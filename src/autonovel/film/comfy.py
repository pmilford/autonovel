"""A small client for a local ComfyUI server, and the keyframe workflows.

ComfyUI (GPL-3.0; its outputs are the user's) runs the image model in its
own process on the user's GPU; this module only posts API-format workflows
to it over HTTP and fetches the results. Nothing here loads a model.

The default workflow is FLUX 3 Image Klein (distilled), the stack's pick
for keyframes and multi-reference character sheets: text to image when a
frame has no references, `ReferenceMultiLatent` edit when it has (up to ten
reference images, e.g. a character's front view for the three-quarter and
profile views, or the sheets of everyone in a shot). Model file names are
the server's own and can be overridden (`--unet`, `--clip`, `--vae`).

Safety, because a crashed WSL loses work: `wait()` interrupts the job when
system RAM in use (total minus available) passes `ram_limit_gb`, and
`free()` asks the server to unload its models when a batch ends, so an idle
server does not sit on 12 GB of RAM. Start the server with
`--disable-pinned-memory` under WSL.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_URL = os.environ.get("AUTONOVEL_COMFY_URL", "http://127.0.0.1:8188")

KLEIN = {
    "unet": os.environ.get("AUTONOVEL_KLEIN_UNET", "flux3-image-klein-int8-convrot.safetensors"),
    "clip": os.environ.get("AUTONOVEL_KLEIN_CLIP", "qwen3vl_4b_int8_convrot.safetensors"),
    "clip_type": "flux3",
    "vae": os.environ.get("AUTONOVEL_KLEIN_VAE", "flux2-vae.safetensors"),
    "steps": 16,
    "cfg": 1.0,
    "shift": 2.77259,
    "label": "FLUX 3 Image Klein (distilled), local ComfyUI",
    "licence": "FLUX Kommunity v1.0: non-commercial use free; outputs commercial only under US$5M revenue, "
               "with filtering or human review and AI disclosure",
}


class ComfyError(RuntimeError):
    pass


class RamLimitExceeded(ComfyError):
    pass


def ram_used_gb() -> float | None:
    """System RAM in use (total - available), from /proc/meminfo; None off Linux."""
    try:
        info = {}
        for ln in Path("/proc/meminfo").read_text().splitlines():
            k, v = ln.split(":", 1)
            info[k] = int(v.split()[0])
        return (info["MemTotal"] - info["MemAvailable"]) / 2**20
    except (OSError, KeyError, ValueError):
        return None


@dataclass
class Client:
    url: str = DEFAULT_URL
    timeout_s: float = 600.0
    ram_limit_gb: float | None = None
    peak_ram_gb: float = 0.0
    log: list[str] = field(default_factory=list)

    def _http(self):
        import httpx
        return httpx.Client(base_url=self.url, timeout=60.0)

    def up(self) -> dict | None:
        try:
            with self._http() as c:
                r = c.get("/system_stats")
                return r.json() if r.status_code == 200 else None
        except Exception:
            return None

    def upload_image(self, path: Path) -> str:
        """Put a reference image in the server's input folder (content-named,
        so the same file uploaded twice is one file)."""
        import hashlib
        data = path.read_bytes()
        name = f"autonovel_{hashlib.sha256(data).hexdigest()[:16]}{path.suffix.lower() or '.png'}"
        with self._http() as c:
            r = c.post("/upload/image", files={"image": (name, data, "image/png")},
                       data={"overwrite": "true", "type": "input"})
        if r.status_code != 200:
            raise ComfyError(f"upload of {path} failed: HTTP {r.status_code} {r.text[:300]}")
        return r.json().get("name", name)

    def queue(self, workflow: dict) -> str:
        with self._http() as c:
            r = c.post("/prompt", json={"prompt": workflow, "client_id": str(uuid.uuid4())})
        if r.status_code != 200:
            raise ComfyError(f"the server refused the workflow: HTTP {r.status_code} {r.text[:1500]}")
        return r.json()["prompt_id"]

    def interrupt(self) -> None:
        try:
            with self._http() as c:
                c.post("/interrupt", json={})
        except Exception:
            pass

    def wait(self, prompt_id: str) -> dict:
        """Poll until the job finishes; returns its outputs. Interrupts and
        raises when RAM passes the limit or the job runs past the timeout."""
        t0 = time.time()
        with self._http() as c:
            while True:
                used = ram_used_gb()
                if used is not None:
                    self.peak_ram_gb = max(self.peak_ram_gb, used)
                    if self.ram_limit_gb and used > self.ram_limit_gb:
                        self.interrupt()
                        raise RamLimitExceeded(f"system RAM in use {used:.1f} GB passed the limit of "
                                               f"{self.ram_limit_gb:g} GB; the job was interrupted")
                if time.time() - t0 > self.timeout_s:
                    self.interrupt()
                    raise ComfyError(f"job {prompt_id} ran past {self.timeout_s:g} s and was interrupted")
                h = c.get(f"/history/{prompt_id}").json()
                if prompt_id in h:
                    status = h[prompt_id].get("status", {})
                    if status.get("status_str") == "error":
                        msgs = [m for m in status.get("messages", []) if m and m[0] == "execution_error"]
                        detail = msgs[0][1] if msgs else status
                        if isinstance(detail, dict):
                            detail = {k: detail.get(k) for k in ("node_type", "exception_type", "exception_message")}
                        raise ComfyError(f"job {prompt_id} failed: {detail}")
                    if status.get("completed") or status.get("status_str") == "success":
                        return h[prompt_id].get("outputs", {})
                time.sleep(0.5)

    def fetch_images(self, outputs: dict, key: str = "images") -> list[bytes]:
        """The files a job saved under `key` (`images`, or `audio` for a
        sound job), in node order."""
        out = []
        with self._http() as c:
            for node in outputs.values():
                for im in node.get(key, []) or []:
                    r = c.get("/view", params={"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                               "type": im.get("type", "output")})
                    if r.status_code == 200:
                        out.append(r.content)
        return out

    def free(self) -> bool:
        """Ask the server to unload its models and free memory."""
        try:
            with self._http() as c:
                r = c.post("/free", json={"unload_models": True, "free_memory": True})
            return r.status_code == 200
        except Exception:
            return False


def klein_workflow(prompt: str, *, width: int, height: int, seed: int, refs: list[str] | None = None,
                   prefix: str = "autonovel/frame", models: dict | None = None,
                   megapixels: float = 1.0) -> dict:
    """FLUX 3 Klein distilled: text to image, or a multi-reference edit when
    `refs` (names already in the server's input folder) are given."""
    m = {**KLEIN, **(models or {})}
    wf: dict = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": m["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": m["clip"], "type": m["clip_type"],
                                                      "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": m["vae"]}},
        "4": {"class_type": "ModelSamplingFlux", "inputs": {"model": ["1", 0], "max_shift": m["shift"],
                                                             "base_shift": m["shift"], "width": width,
                                                             "height": height}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
        "7": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height,
                                                                 "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "positive": ["5", 0], "negative": ["6", 0],
                                                    "latent_image": ["7", 0], "seed": int(seed),
                                                    "steps": int(m["steps"]), "cfg": float(m["cfg"]),
                                                    "sampler_name": "euler", "scheduler": "simple",
                                                    "denoise": 1.0}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": prefix}},
    }
    if refs:
        ref_node: dict = {"positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0],
                          "resolution": "resize", "resolution.megapixels": float(megapixels)}
        for k, name in enumerate(refs[:10]):
            nid = str(200 + k)
            wf[nid] = {"class_type": "LoadImage", "inputs": {"image": name}}
            ref_node[f"images.image{k}"] = [nid, 0]
        wf["11"] = {"class_type": "ReferenceMultiLatent", "inputs": ref_node}
        wf["8"]["inputs"]["positive"] = ["11", 0]
        wf["8"]["inputs"]["negative"] = ["11", 1]
    return wf


STABLE_AUDIO = {
    "ckpt": os.environ.get("AUTONOVEL_SA_CKPT", "stable_audio_3_medium.safetensors"),
    "clip": os.environ.get("AUTONOVEL_SA_CLIP", "t5gemma_b_b_ul2.safetensors"),
    "steps": 8,
    "label": "Stable Audio 3 Medium, local ComfyUI",
    "licence": "Stability AI Community: free under US$1M revenue, outputs commercial; Gemma terms on the encoder",
}


def stable_audio_workflow(prompt: str, *, seconds: float, seed: int, prefix: str = "autonovel/sound",
                          models: dict | None = None) -> dict:
    """Stable Audio 3 Medium: text to a sound cue (ambience, effects)."""
    m = {**STABLE_AUDIO, **(models or {})}
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": m["ckpt"]}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": m["clip"], "type": "stable_audio",
                                                      "device": "default"}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
        "5": {"class_type": "EmptyLatentAudio", "inputs": {"seconds": float(seconds), "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["3", 0], "negative": ["4", 0],
                                                    "latent_image": ["5", 0], "seed": int(seed),
                                                    "steps": int(m["steps"]), "cfg": 1.0, "sampler_name": "lcm",
                                                    "scheduler": "simple", "denoise": 1.0}},
        "7": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveAudio", "inputs": {"audio": ["7", 0], "filename_prefix": prefix}},
    }


def dump(workflow: dict) -> str:
    return json.dumps(workflow, indent=1)
