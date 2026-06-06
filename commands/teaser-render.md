---
name: autonovel:teaser-render
description: Render the teaser's shot prompts into actual clips via a free, no-key backend (Pollinations), then run a vision critique that marks each clip KEEP / REGENERATE / UPGRADE-TO-PAID. Stateless — clips land on disk, nothing is assembled.
argument-hint: "--book <short-name> [--provider pollinations|veo|sora|runway|luma] [--kind image|video] [--takes <n>] [--shot <id>] [--height <px>] [--dry-run]"
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
leaves text behind. The default backend is **Pollinations**: free, no
API key, no signup (PRD §22). Watermarks and low resolution are fine for
the dev passes this is built for; upgrade individual shots to a paid
provider only where the free clip can't carry the moment.

It is deliberately **thin** (PRD §23.2):

  - **Stateless.** Clips land in `books/{book}/teaser/clips/` and that's
    it — no state file, no manifest the rest of the pipeline depends on.
    Re-running just re-downloads.
  - **No assembly.** This stops at per-shot clip files. Stitching them
    into one video is a separate step (`/autonovel:teaser-assemble`).
  - **Free + `--dry-run`.** `--dry-run` prints the exact request plan
    (every URL) without spending a byte; the live run is free on
    Pollinations.

After rendering it runs a **vision clip critique** — the quality half of
the loop the mechanical linter can't do (PRD §24.3): it looks at each
clip and marks it **KEEP**, **REGENERATE** (re-run with another take —
identity drift, garbled frame, wrong action), or **UPGRADE-TO-PAID** (the
free backend can't do this shot; flag it for veo/sora/runway). The
verdicts go in an advisory report, never an automatic re-spend.
</purpose>

<workflow>
**Read-failure policy.** `books/{book}/teaser/teaser.json` is
load-bearing — stop if it is missing (run `/autonovel:shot-prompts` or
`/autonovel:teaser` first). Do not retry other reads.

1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--provider <name>`, `--kind image|video` (default `image` — the
   reliable free keyframe path; `video` is experimental on the free
   backend), `--takes <n>` (default 1; over-generate and pick best),
   `--shot <id>` (render just one), `--height <px>` (default 480),
   `--dry-run`. Confirm the book exists in `project.yaml`.

2. **Resolve the provider.** `bash`:
   `autonovel mechanical resolve-video-provider --project-yaml project.yaml [--cli-provider <name>]`
   Read the JSON `{provider, source}`. This is the precedence twin of the
   image resolver: CLI flag → `project.yaml :: video.provider` →
   `pollinations`.

3. **Plan first (always show the cost = $0).** `bash`:
   `autonovel mechanical teaser-render books/{book}/teaser/teaser.json --provider <name> --kind <kind> --takes <n> --height <px> --dry-run --format json`
   Summarise the plan: clip count (= shots × takes), kind, provider,
   output dir. If `--dry-run` was passed, print the plan and **stop here**
   — write nothing.

4. **Render.** `bash` (omit `--dry-run`):
   `autonovel mechanical teaser-render books/{book}/teaser/teaser.json --provider <name> --kind <kind> --takes <n> --height <px> [--shot <id>] --out-dir books/{book}/teaser/clips --format json`
   Parse the JSON results (per-clip `{shot_id, out_path, ok, bytes, error}`).
   Failures are isolated — note them; do not abort. The download is free.

5. **Vision clip critique** (PRD §24.3 — `--kind image` keyframes;
   for `--kind video` review is manual, note that in the report). For each
   successfully-rendered clip, `file_read` the image and judge it against
   the shot's prompt and `docs/teaser-craft.md` §9 (common failures:
   identity drift, melting/extra limbs, garbled text, wrong action,
   physics breaks). Assign one verdict:
   - **KEEP** — usable; on-prompt; subject identity holds.
   - **REGENERATE** — re-run this shot with another take (a fixable
     model wobble). Give the one concrete reason.
   - **UPGRADE-TO-PAID** — the free backend structurally can't do this
     shot (complex action, legible text needed, fine identity at scale);
     recommend a paid provider (veo/sora/runway) for this shot only.

6. **Write `books/{book}/teaser/clips/render-report.md`** — advisory only
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

7. Print a one-screen summary: clips rendered/failed, verdict counts
   (KEEP / REGENERATE / UPGRADE-TO-PAID), and the next step:

   ```
   🎞️  Rendered {ok}/{total} clips → books/{book}/teaser/clips/ ({provider}, free).
        KEEP {k} · REGENERATE {r} · UPGRADE-TO-PAID {u}.

   Re-run the REGENERATE shots free:
     /autonovel:teaser-render --book {book} --shot <id> --takes 3
   Then assemble (Phase 3): /autonovel:teaser-assemble --book {book}
   ```
</workflow>

<acceptance>
- Clips are written under `books/{book}/teaser/clips/` (one file per
  shot/take); no state file or manifest is created that other commands
  depend on, and nothing is assembled into a single video.
- `--dry-run` prints the full request plan (every URL) and writes nothing.
- The default provider is the free `pollinations` (resolved via
  `resolve-video-provider`); a failed clip download never aborts the batch.
- `books/{book}/teaser/clips/render-report.md` exists with a per-clip
  verdict (KEEP / REGENERATE / UPGRADE-TO-PAID) for each rendered image
  clip, plus any failed downloads.
- No paid provider is ever called automatically; UPGRADE-TO-PAID is a
  recommendation in the report, not an action.
</acceptance>
