---
name: autonovel:teaser-refs
description: Develop and approve character/location reference images for a teaser before spending a real render. Declares a source per recurring subject (public-domain art, a local image, or generate), locks the appearance, and gates real generation behind an approval step. Mechanical status + scaffold in Python; sourcing/approval here.
argument-hint: "--book <short-name> [--init] [--subject <NAME>] [--approve <NAME>] [--force]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/teaser/teaser.json
writes:
  - books/{book}/teaser/refs.yaml
context_mode: book
---

<purpose>
Character and location identity drifts across separately-generated clips.
The fix is a **canonical reference image per recurring subject**, fed as
the first frame / reference of every clip with that subject, plus the same
locked appearance string in every prompt. This command develops those
references *deliberately* and **gates real spending behind approval**:

  - **Declare a source** per subject — a public-domain painting/sketch
    (e.g. Dürer's *Portrait of Jakob Fugger*, or the Matthäus Schwarz
    *Klaidungsbüchlein* costume sketches), a local image you provide, or
    `generate` (make one with the art pipeline).
  - **Lock the appearance + constraints** (period dress, age, likeness)
    so every shot prompt is consistent.
  - **Approve** each reference before any quota-bearing render uses it.
    The offline `stub` backend is exempt — rehearse the whole flow free.

The mechanical half (manifest schema, scaffold, approval status, the
"next action" per subject) lives in `autonovel mechanical teaser-refs`;
the sourcing (PD fetch / import / generate) and the *approval decision*
are the steps here. Quality/likeness is judged by you + the LLM, never by
a Python heuristic.
</purpose>

<workflow>
**Read-failure policy.** `books/{book}/teaser/teaser.json` is
load-bearing — stop if it is missing (run `/autonovel:teaser` or
`/autonovel:shot-prompts` first). Do not retry other reads.

1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--init` (scaffold the manifest), `--subject <NAME>` (work one
   subject), `--approve <NAME>` (mark one approved/locked), `--force`.
   Confirm the book exists in `project.yaml`.

2. **Scaffold the manifest if missing.** `bash`:
   `autonovel mechanical teaser-refs books/{book}/teaser/teaser.json --init [--force]`
   This writes `books/{book}/teaser/refs.yaml` with one `pending` subject
   per recurring character, appearance pre-filled. (Skip if it already
   exists and `--init` was not passed.)

3. **Show the approval status.** `bash`:
   `autonovel mechanical teaser-refs books/{book}/teaser/teaser.json --format json`
   Read the per-subject rows: `{subject, source, source_ref, status,
   exists, next_action, shots}`. `next_action` is one of
   `declare-source` / `fetch-source` / `generate` / `approve` / `ready`.

4. **For each subject not `ready`, do its next action** (one at a time;
   honour `--subject` if given):
   - **declare-source** — propose a source for this subject from the
     story + period. For real historical figures, prefer a **public-domain
     portrait/sketch** via `bash`:
     `autonovel mechanical wikimedia-search "<name> portrait"` — pick a
     period-appropriate, PD result and record its `File:…` title. Edit
     `books/{book}/teaser/refs.yaml`: set `source: wikimedia`,
     `source_ref: "File:…"`, a locked `appearance`, and `constraints`
     (period dress, age, likeness limits). For invented characters set
     `source: generate`.
   - **fetch-source** — pull the declared plate to the refs dir. For
     wikimedia: `bash`
     `autonovel mechanical wikimedia-fetch "<File:…>" --output books/{book}/teaser/refs/<slug>.png`
     For a local image, use `/autonovel:art-import` (or copy it to the
     `ref_path`). The plate becomes the morph/consistency anchor.
   - **generate** — create the canonical realistic portrait. Save it as
     `books/{book}/teaser/refs/<slug>_ref.png` (the path `--refs` prefers).
     Best path: `gemini` conditioned on the fetched source —
     `/autonovel:teaser-render --book {book} --shot <one> --provider gemini`
     with the source as a reference — or `/autonovel:art-curate`.
   - **approve** — the plate exists; **show it to the user** (`file_read`)
     against the locked `appearance` + `constraints` and ask them to
     confirm likeness/period. On `--approve <NAME>` (or user assent) edit
     `refs.yaml` to set that subject's `status: locked`.

5. **Re-run the status** (`--format json`) and report. When
   `all_approved` is true, the references are ready to anchor a real
   render.

6. Print a one-screen summary — per subject: source, status, next action —
   and the next step:

   ```
   🎭 References for {book}: {ready}/{total} locked.
      Pending: {subject → next_action, …}

   Next: finish the pending subjects, then render anchored to them with --refs:
     /autonovel:teaser-render --book {book} --provider gemini --kind image --refs
   (Validate free first: /autonovel:teaser-render --book {book} --provider stub)
   ```
</workflow>

<acceptance>
- `books/{book}/teaser/refs.yaml` exists (scaffolded on `--init`) with one
  entry per recurring subject; each has a `source`, locked `appearance`,
  and a `status` (pending → approved → locked).
- The approval status (from `teaser-refs --format json`) drives the work:
  every subject reaches `ready` only when its plate exists on disk **and**
  it is approved/locked.
- Public-domain sources are fetched via `wikimedia-search`/`-fetch`; local
  images via `art-import`; invented characters via `generate`.
- No real (quota-bearing) generation is implied by this command — it only
  develops + approves references. The approval gate is advisory input to
  `/autonovel:teaser-render`; the offline `stub` backend is always exempt.
</acceptance>
