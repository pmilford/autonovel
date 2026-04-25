---
name: autonovel:promote-canon
description: Promote pending canon entries from every book's pending_canon.md into shared/canon.md.
argument-hint: "[--book <short-name>] [--dry-run]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/canon.md
  - shared/world.md
  - shared/characters.md
  - books/*/pending_canon.md
writes:
  - shared/canon.md
  - books/*/pending_canon.md
context_mode: series
---

<purpose>
Move candidate facts out of per-book scratchpads
(`books/{book}/pending_canon.md`) and into the series-wide
`shared/canon.md`. This is the one command that writes `shared/canon.md`
— `/autonovel:revise`, `/autonovel:draft`, and every other chapter
command are forbidden from editing it directly (§19), because two books
drafting chapters in parallel both appending to the same file is a
cross-book race condition.

Single-threading is enforced by `.autonovel/in-progress.lock` (acquired
by the preamble); inside the critical section the command:
1. reads every pending file,
2. de-duplicates against existing canon,
3. rejects contradictions,
4. appends the survivors to `shared/canon.md` with provenance
   (which book / chapter proposed them),
5. empties every pending file it consumed.

The preamble's checkpoint captures both `shared/canon.md` and the
pending files, so `autonovel rollback` undoes the whole promotion.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` restricts the sweep to
   one book's pending file. `--dry-run` prints what would be
   promoted without writing. No positional arguments.

2. Use `file_read` on `project.yaml` to list every book in the
   series. If `--book` is passed, keep only that one; fail with
   `unknown book: <name>` if it is not listed.

3. For each selected book, use `file_read` on
   `books/{book}/pending_canon.md`. Parse it as a plain bullet list
   (each non-empty line starting with `-` is one candidate entry).
   Lines that read `no new facts` (case-insensitive) are skipped —
   they are the `revise` command's placeholder for "I wrote nothing
   new" and carry no payload.

4. Use `file_read` on `shared/canon.md`, `shared/world.md`, and
   `shared/characters.md`. The existing canon is the baseline for
   de-duplication and contradiction detection:
   - **Duplicate**: an entry whose substantive content is already
     stated (possibly in different words) in `shared/canon.md`.
     Discard silently; record it under the per-book discard list
     for the summary.
   - **Contradiction**: an entry that contradicts `shared/canon.md`,
     `shared/world.md`, or `shared/characters.md`. Default-discard
     and record under the per-book conflict list — but with one
     exception below.

     **Exception — research-tagged entries win contradictions.** A
     pending entry carrying a `[research:<slug>]` tag was written
     by `/autonovel:research --from-seed` and is backed by a cited
     primary source (the `[shortname]` next to it resolves in
     `shared/sources.bib`). When such an entry contradicts existing
     canon, prefer the research entry: promote it, AND additionally
     emit a `## Superseded <UTC-date>` block in `shared/canon.md`
     listing the prior canonical line and a one-sentence rationale
     ("research note `<slug>` cites [<shortname>] for <new value>;
     prior value was <old value>"). The user reviewing
     `shared/canon.md` then sees both the new fact and the old one
     with a clear paper trail. This is what makes
     `/autonovel:research --from-seed` → `/autonovel:promote-canon`
     a fully automatic update path: research's citations beat the
     LLM's general-knowledge guesses, and the supersedure is
     visible.
   - **Survivor**: neither duplicate nor contradiction. Promote.

5. For each surviving entry, rewrite it into the canonical form:

   ```
   - <fact> (from {book} ch_{chapter:02d})
   ```

   For research-tagged entries, use:

   ```
   - <fact> [shortname] (from research note <slug>)
   ```

   so the citation makes it into the canonical entry. The
   `(from …)` provenance lets future audits trace every canon
   fact back to the chapter or research note that established it.
   If the pending entry already carries a provenance tail, keep it
   verbatim.

6. If `--dry-run`, print a per-book report and stop — do NOT write
   anything. Format:

   ```
   book: {book}
     promoted: N
     duplicates: M
     conflicts:
       - <entry> — contradicts: <canon line>
   ```

7. Otherwise, use `file_write` to append the survivors to
   `shared/canon.md`. Append under a dated heading:
   `## Promoted <UTC-date>` (one heading per invocation). Keep the
   existing body of `shared/canon.md` verbatim; do not rewrite it.

8. Use `file_write` to rewrite each consumed
   `books/{book}/pending_canon.md`. After a successful promotion the
   file contains either:
   - the entries that were rejected as conflicts (so the user sees
     them on the next `autonovel status` check), plus a header
     `# Conflicts — resolve before next promote-canon`, or
   - a single line `no new facts` if every entry was promoted or
     dropped as duplicate.

9. Print a one-screen summary: per-book promoted / duplicates /
   conflict counts, plus the canonical next command
   (`autonovel status` to see remaining conflicts, or the drafting
   step for the next chapter).
</workflow>

<acceptance>
- If `--dry-run`, no files under `shared/` or `books/*/` change.
- Otherwise, `shared/canon.md` contains a `## Promoted <UTC-date>`
  heading with at least one entry, unless every pending file was
  empty or said `no new facts`.
- For every book whose pending file contained only non-conflicting
  entries, `books/{book}/pending_canon.md` ends with `no new facts`.
- Contradictions are never silently merged: they are preserved under
  the `# Conflicts` header in the pending file so the user can
  resolve them by editing canon or the pending file.
</acceptance>
