---
name: autonovel:package
description: End-to-end release builder — PDF + ePub + covers + landing + audiobook, zipped.
argument-hint: "--book <short-name> [--skip <target[,target...]>] [--out <path>]"
model_tier: light
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/typeset/novel.pdf
  - books/{book}/typeset/novel.epub
  - books/{book}/art/cover_titled.png
  - books/{book}/art/cover_print.png
  - books/{book}/art/thumbnails/*.png
  - books/{book}/audiobook/full_audiobook.mp3
  - books/{book}/landing/index.html
writes:
  - books/{book}/release/release.zip
  - books/{book}/release/manifest.json
context_mode: book
---

<purpose>
The release builder. Calls the upstream export commands in order
(covers → typeset → landing → audiobook), then stitches the results
into a single release zip for GitHub release attachments, Gumroad,
IngramSpark uploads, etc.

Light tier — pure orchestration. The command does not generate any
content itself; it surfaces which steps need upstream work and
advises the user how to resume. Every creative step has already been
checked in at this point.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` is required. Optional
   `--skip covers,typeset,audiobook,landing` (comma list of release
   targets to omit — e.g. skip audiobook if no ElevenLabs key).
   `--out <path>` overrides the release zip path (default:
   `books/{book}/release/release.zip`).

2. Use `file_read` on `project.yaml` and enumerate the expected input
   artifacts:
   - Covers: `books/{book}/art/cover_titled.png`,
     `books/{book}/art/cover_print.png`, `thumbnails/*`.
   - Typeset: `books/{book}/typeset/novel.pdf`,
     `books/{book}/typeset/novel.epub`.
   - Audiobook: `books/{book}/audiobook/full_audiobook.mp3` (and
     `full_audiobook.m4b` if present).
   - Landing: `books/{book}/landing/index.html` + `cover.png` +
     `cover_bg.png`.

3. For each expected input that is missing (and whose category is
   not in `--skip`), print one line with the slash-command that
   produces it. Do NOT invoke those commands — this is advisory only.
   If any required input is missing the package command stops after
   printing the remediation list.

4. Build the manifest: a JSON document listing every artifact that
   will be zipped, with path, bytes, and SHA-256. Use
   `python3 -c "..."` via `bash` to compute the hashes in one
   invocation.

5. Use `bash: zip -j -r books/{book}/release/release.zip <inputs...>`
   (or `--out <path>`) to build the release archive. Include the
   manifest at the archive root. Use a deterministic file order so
   the zip is reproducible modulo mtime.

6. Print a one-screen summary: total archive size, file count, and
   the manifest's SHA-256 (for integrity checks). If any `--skip`
   categories were honoured, list them so the user remembers what
   isn't in the zip.
</workflow>

<acceptance>
- `books/{book}/release/release.zip` exists on success.
- `books/{book}/release/manifest.json` is inside the zip and lists
  every file with `path`, `bytes`, and `sha256`.
- If a non-skipped upstream artifact is missing, no zip is created
  and the summary names the slash-command to run.
</acceptance>
