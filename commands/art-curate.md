---
name: autonovel:art-curate
description: Generate image variants from saved directions via the configured image provider. `pollinations` is the free, no-API-key option.
argument-hint: "--book <short-name> --surface cover|ornament|map|scene-break [--provider pollinations|fal|replicate|openai]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/art/visual_style.json
  - books/{book}/art/directions/{surface}.json
writes:
  - books/{book}/art/variants/{surface}_*.png
  - books/{book}/art/picks.json
context_mode: book
---

<purpose>
Replace `gen_art.py curate`. Reads the N saved directions for a surface
and generates one image per direction via the configured provider,
downloading each result into `books/{book}/art/variants/`. The user
then picks one with `/autonovel:art-pick`.

Multi-provider hook is intentional — `project.yaml` can set
`image.provider: pollinations|fal|replicate|openai` and a
per-provider env-var name for the API key.

**Recommended default for new projects: `pollinations`** —
free, no API key, uses Pollinations.ai's open HTTPS endpoint
(`image.pollinations.ai/prompt/<encoded-prompt>?width=W&height=H`).
Quality is roughly SDXL-level; varies. The other providers (fal,
replicate, openai) cost money and need keys but produce more
consistent output. Pick what matches your budget.

Free typography-only path (no AI art at all): skip art-curate
entirely and run `/autonovel:cover-print --typographic-only` —
covers come out as title + author over a solid color or pattern
via Pillow, no provider involved.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` and `--surface` are
   required (same four surfaces as `art-directions`). `--provider`
   defaults to `fal` (or the `image.provider` key in `project.yaml` if
   set). Anything else is a usage error.

2. Use `file_read` on `books/{book}/art/visual_style.json` and
   `books/{book}/art/directions/{surface}.json`. If either is missing,
   surface the command to run first and stop.

3. Resolve the provider's API key (or skip for pollinations):
   - `pollinations` → no key needed; the endpoint is open. Skip
     this step.
   - `fal` → `FAL_KEY`.
   - `replicate` → `REPLICATE_API_TOKEN`.
   - `openai` → `OPENAI_API_KEY`.

   If a paid provider's key is missing, stop with a single-line
   message naming the env var, suggest switching to
   `--provider pollinations` for the free path, and point the
   user at `.env.example`.

4. For each direction, shell out to the provider via `bash` and
   save the returned image to
   `books/{book}/art/variants/{surface}_NN.png` (two-digit index
   matching the direction index). Use these defaults per surface:
   - `cover`: 1K resolution, 2:3 aspect.
   - `ornament`: 0.5K resolution, 1:1 aspect.
   - `map`: 1K resolution, 4:3 aspect.
   - `scene-break`: 0.5K resolution, 4:1 aspect.

   Provider-specific shapes:
   - `pollinations`: GET `https://image.pollinations.ai/prompt/
     <URL-encoded-prompt>?width=W&height=H&seed=<index>&nologo=true`.
     Use `curl -L -o <out>` (the endpoint streams a PNG
     directly). The seed parameter ensures different directions
     produce different images. No request body.
   - `fal` / `replicate` / `openai`: short `curl`/`httpx` POST
     with the prompt — same shape as the pre-rewrite pipeline.

5. Use `file_write` to update `books/{book}/art/picks.json` — the
   registry of what has been generated and what has been picked.
   Structure:
   ```json
   {
     "variants": {
       "cover_01": {"url": "...", "path": "...", "direction": "abstract"}
     },
     "picks": {
       "cover": null
     }
   }
   ```
   Preserve existing `picks` — this step only adds to `variants`.

6. Print a one-screen summary listing every generated variant's
   direction + byte count + path. Emit a trailing
   `next: /autonovel:art-pick --book {book} --surface {surface}
   --variant <N>`.
</workflow>

<acceptance>
- One PNG per direction is written under
  `books/{book}/art/variants/{surface}_*.png`.
- `books/{book}/art/picks.json` lists every new variant under
  `variants`, preserving any previous `picks` entries.
- If the provider's API key env var is missing, no files are written
  and the command exits with a usage message naming the env var.
</acceptance>
