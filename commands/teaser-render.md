---
name: autonovel:teaser-render
description: Render the teaser's shot prompts into actual clips. Free offline `stub` keyframes validate the whole pipeline at zero cost/quota; `grok` (free dialogue+music, no card) is the default real backend. Then a vision critique marks each clip KEEP / REGENERATE / UPGRADE-TO-PAID. Stateless — clips land on disk, nothing is assembled.
argument-hint: "--book <short-name> [--provider stub|grok|kie|veo|magichour|fal|flow|pollinations] [--kind auto|image|video] [--takes <n>] [--shot <id>] [--height <px>] [--token <key>] [--delay <s>] [--dry-run]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/teaser/teaser.json
writes:
  - books/{book}/teaser/clips/render-report.md
context_mode: book
---

<purpose>
Take the shot prompts and produce **actual clips** — the first step that
leaves text behind.

**Spend nothing until the pipeline is proven.** The default real backend
costs limited free generations (grok = 5/day), so the first thing to do
on any new teaser is a **free, offline `stub` render**: it synthesizes a
placeholder keyframe per shot **locally** (no network, no key, no quota)
so you can validate the whole render → cut-list → assemble chain for $0.
Only switch to a real backend once the pipeline works end-to-end.

Backends (capabilities are data — see `docs/teaser-render-providers.md`):

  - **`stub`** — offline placeholder keyframes (Pillow). No network/key/
    quota. **Use this first** to validate the pipeline.
  - **`gemini`** — reference-conditioned photoreal **image keyframes**
    (Nano Banana). With `--refs` every keyframe is conditioned on the
    subject's approved portrait so a character's face holds across shots.
    `--kind image`; needs `GEMINI_API_KEY` (~$0.04/img). The recommended
    way to make the per-shot static keyframes.
  - **`grok`** — DEFAULT real backend. xAI Grok Imagine: native
    dialogue+music, **5 free gens/day + $25 signup, no card**. Needs a
    free `XAI_API_KEY`.
  - **`kie`** — kie.ai reseller, one key fronts Veo3/Kling/Grok/Seedance
    (all with audio); 80 free credits, no card. `KIE_API_KEY`.
  - **`veo`** — Veo via the Gemini API (native audio, top quality;
    paid/$300-GCP-credit). `GEMINI_API_KEY`.
  - **`magichour`** — recurring free (100/day, no card) but **silent**
    (layer an audio bed in `/autonovel:teaser-assemble`). `MAGICHOUR_API_KEY`.
  - **`fal`** — fal.ai, $20 one-time credit, no card. `FAL_KEY`.
  - **`flow`** — **manual** (Google Flow GUI on AI Pro — no API). Render
    by hand, drop the MP4s in `clips/`; assembly stitches them.
  - **`pollinations`** — free **flux keyframe IMAGES** only (its free
    video is gone). Now needs a free account token (`POLLINATIONS_TOKEN`).

**Reference-conditioned keyframes (`--refs`).** Pass `--refs` to feed each
shot's **approved** character/location references (from `refs.yaml`, via
`/autonovel:teaser-refs`) into reference-capable backends (`gemini`, `fal`
kontext, `pollinations` flux-kontext) so identity holds across shots. Only
approved/locked subjects flow (the approval gate); pending ones are
skipped with a warning. `--film-style "<style>"` swaps the book's
typeset art style for a photoreal film look without editing teaser.json.

**Image-to-video (`--from-keyframes`).** The two-stage path that keeps
identity AND adds motion: first render reference-conditioned **keyframes**
(`--kind image --refs`), then render **video** with `--from-keyframes` —
each shot animates from its own `shot_<id>.png` as the start frame
(`grok`/`veo`/`kie`). A shot with no keyframe just falls back to
text-to-video. `--keyframe-dir` points elsewhere (default: the clips dir).

Keys come from `--token`, then the matching env var, then a project-local
`.env` (see `docs/teaser-render-providers.md`). Watermarks and low
resolution are fine for the dev passes this is built for; upgrade
individual shots to a paid provider only where the free clip can't carry
the moment.

It is deliberately **thin** (PRD §23.2):

  - **Stateless.** Clips land in `books/{book}/teaser/clips/` and that's
    it — no state file, no manifest the rest of the pipeline depends on.
    Re-running just re-downloads.
  - **No assembly.** This stops at per-shot clip files. Stitching them
    into one video is a separate step (`/autonovel:teaser-assemble`).
  - **`--dry-run`** prints the exact request plan **and reports whether a
    key is present** for the resolved provider — without spending
    anything. Requests are paced ≥ the provider's polite interval with
    automatic 429/503 backoff.

After rendering it runs a **vision clip critique** — the quality half of
the loop the mechanical linter can't do (PRD §24.3): it looks at each
clip and marks it **KEEP**, **REGENERATE** (re-run with another take —
identity drift, garbled frame, wrong action), or **UPGRADE-TO-PAID** (the
free backend can't do this shot; flag it for veo/kie). The verdicts go in
an advisory report, never an automatic re-spend.
</purpose>

<workflow>
**Read-failure policy.** `books/{book}/teaser/teaser.json` is
load-bearing — stop if it is missing (run `/autonovel:shot-prompts` or
`/autonovel:teaser` first). Do not retry other reads.

1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--provider <name>`, `--kind auto|image|video` (default `auto` —
   image for `stub`/`pollinations`, video for the video backends),
   `--takes <n>` (default 1; over-generate and pick best), `--shot <id>`
   (render just one), `--height <px>` (default 480), `--token <key>`,
   `--delay <s>` (override the polite inter-request interval), `--dry-run`.
   Confirm the book exists in `project.yaml`.

2. **Validate the pipeline FREE first (unless the user named a provider).**
   If no `--provider` was passed and `books/{book}/teaser/clips/` has no
   clips yet, do a **`stub` render** so the user sees the full chain work
   at zero cost/quota before spending a real backend. Tell them you're
   doing this and why:
   `autonovel mechanical teaser-render books/{book}/teaser/teaser.json --provider stub --out-dir books/{book}/teaser/clips --format json`
   Then point them at `/autonovel:teaser-assemble` to confirm the stitch,
   and stop — or continue to step 3 if they explicitly asked for a real
   render.

3. **Resolve the provider.** `bash`:
   `autonovel mechanical resolve-video-provider --project-yaml project.yaml [--cli-provider <name>]`
   Read the JSON `{provider, source}`. Precedence: CLI flag →
   `project.yaml :: video.provider` → `grok` (free default). Note:
   `grok` is the *video* default; `pollinations` remains the *image*
   keyframe default (`resolve-image-provider`).

4. **Plan first (always show the cost + key status).** `bash`:
   `autonovel mechanical teaser-render books/{book}/teaser/teaser.json --provider <name> --kind <kind> --takes <n> --height <px> --dry-run --format json`
   The JSON includes `{provider, kind, needs_key, key_present, manual,
   free_note, requests}`. Summarise: clip count (= shots × takes), kind,
   provider, output dir, and **whether a key is present**. If `--dry-run`
   was passed, print the plan and **stop here** — write nothing.

5. **Key / manual / approval gates.**
   - **Approval gate (real renders only; `stub` is exempt).** Before
     spending a quota-bearing backend, check character references: `bash`
     `autonovel mechanical teaser-refs books/{book}/teaser/teaser.json --format json`
     If `all_approved` is false, warn which subjects aren't locked yet and
     recommend `/autonovel:teaser-refs --book {book}` first (identity will
     drift without locked references). This is advisory — proceed if the
     user insists, but say so.
   - If `manual` is true (`flow`): print the manual instructions — render
     the shots in Flow (labs.google/flow), export each MP4, drop them in
     `books/{book}/teaser/clips/` as `shot_<id>.mp4`, then run
     `/autonovel:teaser-assemble`. Stop (no HTTP call is made).
   - If `needs_key` is true and `key_present` is false: stop and tell the
     user exactly which key to set (see `docs/teaser-render-providers.md`),
     e.g. for grok: a free `XAI_API_KEY` from x.ai in `.env`. Do not
     attempt the render.

6. **Render.** `bash` (omit `--dry-run`):
   `autonovel mechanical teaser-render books/{book}/teaser/teaser.json --provider <name> --kind <kind> --takes <n> --height <px> [--shot <id>] [--token <key>] [--delay <s>] --out-dir books/{book}/teaser/clips --format json`
   Parse the JSON results (per-clip `{shot_id, out_path, ok, bytes,
   error}`). Failures are isolated per clip — note them; do not abort. A
   **402/auth** error stops the batch (the key wall hits every shot the
   same way) — surface its one actionable message verbatim.

7. **Vision clip critique** (PRD §24.3 — `--kind image`/stub keyframes;
   for `--kind video` review is manual, note that in the report). For each
   successfully-rendered clip, `file_read` the file and judge it against
   the shot's prompt and `docs/teaser-craft.md` §9 (common failures:
   identity drift, melting/extra limbs, garbled text, wrong action,
   physics breaks). Assign one verdict:
   - **KEEP** — usable; on-prompt; subject identity holds.
   - **REGENERATE** — re-run this shot with another take (a fixable
     model wobble). Give the one concrete reason.
   - **UPGRADE-TO-PAID** — the free backend structurally can't do this
     shot (complex action, legible text needed, fine identity at scale);
     recommend a paid provider (veo/kie) for this shot only.
   (For `stub` clips, the critique is trivially KEEP — they are
   placeholders to prove the pipeline, not final art.)

8. **Write `books/{book}/teaser/clips/render-report.md`** — advisory only
   (NOT a manifest; nothing reads it back):

   ```markdown
   # {Display Title} — Teaser render report

   *Provider:* {provider} · *Kind:* {kind} · *Clips:* {ok}/{total} rendered
   · *Output:* books/{book}/teaser/clips/

   ## Verdicts
   | Shot | Take | Verdict | Reason |
   |---|---|---|---|
   | 01a | 1 | KEEP | on-prompt, identity holds |
   | 02b | 1 | REGENERATE | hands distorted — re-take |
   | 07  | 1 | UPGRADE-TO-PAID | legible signage needed |

   ## Failed downloads
   {shot ids + error, or "none".}

   ## Next
   {which shots to re-run (free) and which to escalate to a paid provider.}
   ```

9. Print a one-screen summary: clips rendered/failed, verdict counts
   (KEEP / REGENERATE / UPGRADE-TO-PAID), and the next step:

   ```
   🎞️  Rendered {ok}/{total} clips → books/{book}/teaser/clips/ ({provider}).
        KEEP {k} · REGENERATE {r} · UPGRADE-TO-PAID {u}.

   Validate the stitch (free): /autonovel:teaser-assemble --book {book}
   Re-run the REGENERATE shots:
     /autonovel:teaser-render --book {book} --shot <id> --takes 3
   ```
</workflow>

<acceptance>
- Clips are written under `books/{book}/teaser/clips/` (one file per
  shot/take); no state file or manifest is created that other commands
  depend on, and nothing is assembled into a single video.
- A fresh teaser can be validated end-to-end for **$0 and zero quota**
  via the offline `stub` provider before any real backend is spent.
- `--dry-run` prints the full request plan and reports `key_present` for
  the resolved provider, and writes nothing.
- The default *video* provider is the free `grok` (resolved via
  `resolve-video-provider`); `pollinations` is image-keyframes only. A
  failed clip download never aborts the batch; a 402/auth wall stops it
  with one actionable message.
- Manual providers (`flow`) make no HTTP call — they print import
  instructions instead.
- `books/{book}/teaser/clips/render-report.md` exists with a per-clip
  verdict (KEEP / REGENERATE / UPGRADE-TO-PAID) for each rendered clip,
  plus any failed downloads.
- No paid provider is ever called automatically; UPGRADE-TO-PAID is a
  recommendation in the report, not an action.
</acceptance>
