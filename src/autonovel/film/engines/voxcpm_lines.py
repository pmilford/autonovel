"""Table-read engine: VoxCPM2 (OpenBMB, Apache-2.0) lines, Whisper-checked.

This script runs in its own Python environment (the one with `voxcpm`,
`faster_whisper`, `torch`, `soundfile`, `librosa`), never inside autonovel:
`autonovel mechanical table-read` writes a job file and runs

    <tts python> voxcpm_lines.py job.json

It imports nothing from autonovel. It does two things:

1. **Casts each voice without anyone's real voice.** A speaker with no
   reference clip gets one made by VoxCPM2's voice design: the model is
   given a written description of the voice ("a fourteen-year-old boy, a
   light clear voice on the edge of breaking ...") and a neutral sentence,
   several seeds are tried, and the take Whisper hears best at a natural
   pace is kept as the speaker's reference (`<ref>.wav` + `<ref>.txt`, its
   exact words). No person's recording is used, so there is nothing to
   consent to; the voice is the description's.
2. **Reads each line in that voice** by cloning the reference, transcribes
   the take with faster-whisper and re-renders it with a new seed (up to
   `tries`) when words are inserted, dropped or changed (VoxCPM2 sometimes
   says words not in the script) or the pace is implausible. Names the
   transcriber can't spell are not errors. The best take is kept.

It prints one JSON object (the result) on its last line of stdout.
"""

import difflib
import json
import os
import re
import sys
import time
import unicodedata


def ascii_fold(t):
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
        "sixteen seventeen eighteen nineteen").split()
TENS = {20: "twenty", 30: "thirty", 40: "forty", 50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty",
        90: "ninety"}


def n2w(k):
    if k < 20:
        return [ONES[k]]
    if k < 100:
        return [TENS[k - k % 10]] + ([ONES[k % 10]] if k % 10 else [])
    if k < 1000:
        return [ONES[k // 100], "hundred"] + (n2w(k % 100) if k % 100 else [])
    if k < 1000000:
        return n2w(k // 1000) + ["thousand"] + (n2w(k % 1000) if k % 1000 else [])
    return [str(k)]


def norm(s):
    s = ascii_fold(s.lower().replace("’", "'").replace("‘", "'"))
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s)
    out = []
    for w in re.sub(r"[^a-z0-9' ]+", " ", s).split():
        w = w.strip("'")
        if not w:
            continue
        out += n2w(int(w)) if w.isdigit() else [w]
    # "a hundred" / "one hundred" are the same number
    return ["one" if (w == "a" and i + 1 < len(out) and out[i + 1] in ("hundred", "thousand")) else w
            for i, w in enumerate(out)]


def compare(text, heard, names):
    R, H = norm(text), norm(heard)
    ins = dele = sub = 0
    notes = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=R, b=H, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        rs, hs = R[i1:i2], H[j1:j2]
        if "".join(rs).replace("'", "") == "".join(hs).replace("'", ""):
            continue
        note = f"{op}:[{' '.join(rs)}]->[{' '.join(hs)}]"
        if op == "replace" and any(re.sub(r"'s?$", "", w) in names for w in rs) and len(hs) <= 2 * len(rs) + 1:
            sub += len(rs)
            notes.append(note + " name")
            continue
        sub += min(len(rs), len(hs))
        ins += max(0, len(hs) - len(rs))
        dele += max(0, len(rs) - len(hs))
        notes.append(note)
    return ins, dele, sub, notes, len(R)


def main():
    job = json.load(open(sys.argv[1], encoding="utf-8"))
    os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
    import numpy as np
    import soundfile as sf
    import torch
    import torchaudio
    import librosa
    from faster_whisper import WhisperModel
    from voxcpm import VoxCPM

    gpu = int(job.get("gpu", 0))
    torch.cuda.set_device(gpu)
    t_load = time.time()
    model = VoxCPM.from_pretrained(job.get("model", "openbmb/VoxCPM2"), load_denoiser=False, optimize=False,
                                   device=f"cuda:{gpu}")
    tm = model.tts_model
    SR = tm.sample_rate
    asr = WhisperModel(job.get("asr_model", "medium.en"), device="cuda", device_index=gpu, compute_type="float16")
    load_s = time.time() - t_load
    names = {w.lower() for w in job.get("names", [])}
    cfg = float(job.get("cfg", 2.0))
    steps = int(job.get("steps", 10))
    tries = int(job.get("tries", 4))

    def gen(text, cache):
        res = tm._generate_with_prompt_cache(target_text=re.sub(r"\s+", " ", text), prompt_cache=cache, min_len=2,
                                             max_len=4096, inference_timesteps=steps, cfg_value=cfg,
                                             retry_badcase=True, retry_badcase_max_times=3,
                                             retry_badcase_ratio_threshold=6.0, streaming=False)
        wav, _, _ = next(res)
        res.close()
        return wav.squeeze(0).float().cpu().numpy()

    def trim(a):
        t, _ = librosa.effects.trim(a, top_db=40, frame_length=1024, hop_length=256)
        pad = np.zeros(int(0.06 * SR), dtype=np.float32)
        return np.concatenate([pad, t.astype(np.float32), pad])

    def hear(a):
        a16 = torchaudio.functional.resample(torch.from_numpy(a), SR, 16000).numpy()
        segs, _ = asr.transcribe(a16, beam_size=5, condition_on_previous_text=False)
        return " ".join(s.text for s in segs).strip()

    def judge(text, a):
        heard = hear(a)
        ins, dele, sub, notes, n = compare(text, heard, names)
        wps = n / max(0.1, len(a) / SR)
        bad_pace = n >= 4 and not ((1.4 if n >= 10 else 1.1) <= wps <= 4.2)
        ok = ins + dele == 0 and not bad_pace
        score = 3 * (ins + dele) + 0.25 * sub + (5 if bad_pace else 0)
        return ok, score, {"heard": heard, "ins": ins, "del": dele, "sub": sub, "wps": round(wps, 2),
                           "bad_pace": bad_pace, "notes": notes}

    result = {"engine": "voxcpm2", "model": job.get("model", "openbmb/VoxCPM2"),
              "asr": job.get("asr_model", "medium.en"), "sample_rate": SR, "gpu": gpu,
              "load_s": round(load_s, 1), "voices": {}, "lines": {}}
    t0 = time.time()
    torch.manual_seed(0)
    gen("Warm up the model, please.", None)

    # 1. Voices: design a reference where there is none.
    caches = {}
    for cue, v in job["voices"].items():
        ref, ref_txt = v["ref"], v["ref"][:-4] + ".txt"
        made = None
        if not os.path.exists(ref) or v.get("remake"):
            best = None
            for attempt in range(int(v.get("design_tries", 4))):
                torch.manual_seed(int(v.get("seed", 7)) + attempt)
                a = trim(gen(f"({v['design']}){v['ref_text']}", None))
                ok, score, info = judge(v["ref_text"], a)
                dur = len(a) / SR
                score += 0 if 3.0 <= dur <= 12.0 else 4
                if best is None or score < best[0]:
                    best = (score, a, attempt, ok, info)
                if ok and score == 0:
                    break
            os.makedirs(os.path.dirname(ref), exist_ok=True)
            sf.write(ref, best[1], SR)
            with open(ref_txt, "w", encoding="utf-8") as fh:
                fh.write(v["ref_text"])
            made = {"attempt": best[2], "passed": best[3], "heard": best[4]["heard"],
                    "duration_s": round(len(best[1]) / SR, 2)}
        ref_text = open(ref_txt, encoding="utf-8").read().strip() if os.path.exists(ref_txt) else v["ref_text"]
        caches[cue] = tm.build_prompt_cache(prompt_text=ref_text, prompt_wav_path=ref, reference_wav_path=ref)
        result["voices"][cue] = {"ref": ref, "made": made}
        print(f"voice {cue}: {'designed' if made else 'reference on file'}", file=sys.stderr, flush=True)

    # 2. Lines.
    for ln in job["lines"]:
        spoken = ln.get("spoken") or ln["text"]
        best, takes = None, []
        for attempt in range(tries):
            torch.manual_seed(1000 + attempt + int(ln.get("seed_offset", 0)))
            a = trim(gen(spoken, caches[ln["cue"]]))
            ok, score, info = judge(ln["text"], a)
            takes.append({"attempt": attempt, "ok": ok, "score": score, "dur_s": round(len(a) / SR, 2), **info})
            if best is None or score < best[0]:
                best = (score, a, attempt, ok)
            if ok:
                break
        os.makedirs(os.path.dirname(ln["out"]), exist_ok=True)
        tmp = ln["out"] + ".part.wav"
        sf.write(tmp, best[1], SR)
        os.replace(tmp, ln["out"])
        result["lines"][ln["id"]] = {"file": ln["out"], "duration_s": round(len(best[1]) / SR, 2),
                                     "attempts": len(takes), "kept": best[2], "passed": best[3],
                                     "heard": takes[best[2]]["heard"], "notes": takes[best[2]]["notes"],
                                     "takes": takes}
        print(f"{ln['id']}: tries={len(takes)}{'' if best[3] else '  NEVER PASSED'}", file=sys.stderr, flush=True)
    result["generation_s"] = round(time.time() - t0, 1)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
