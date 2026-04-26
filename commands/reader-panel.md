---
name: autonovel:reader-panel
description: Four-persona reader panel review of a book's complete arc.
argument-hint: "--book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/*.md
writes:
  - books/{book}/edit_logs/reader_panel.json
context_mode: book
---

<purpose>
Four distinct reader personas review the whole book and answer the same
ten questions. Where they disagree, that's where the editorial decisions
live. Use this after a full revision cycle, when you need signal on
structural problems (momentum, earned ending, thinnest character) that
single-chapter evaluation can't see.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--book <short-name>`. Missing is a
   usage error — print a one-line reminder and stop.

2. Use `file_read` on `project.yaml` and `books/{book}/outline.md` for
   scaffolding. Also `file_read` `books/{book}/voice.md` and parse a
   `## Part 3 — Custom rubric` (or `## Custom rubric`) section the
   same way `/autonovel:evaluate` does — strip the HTML comment
   placeholder, treat top-level bullets as the book-specific
   criteria. Empty or absent → skip; many books have no custom
   rubric and that's fine.

3. Use `file_read` to glob `books/{book}/chapters/*.md`. Build an arc
   summary inline: for each chapter, emit its number, word count, the
   first ~500 chars (opening), the last ~500 chars (closing), and its
   outline beats. This is the material the four personas share; do
   not send the full prose to every persona — the arc summary is
   enough and keeps the context affordable.

4. Run four sequential LLM calls, each with a distinct system prompt:

   - **The Editor** — senior fiction editor, 200+ novels. Prose texture,
     subtext, sentence-level craft, over-explaining, borrowed vs earned
     metaphor. Not cruel but precise.
   - **The Genre Reader** — 50+ novels a year in this genre. Pacing,
     mystery, worldbuilding payoff, wanting-to-turn-the-page. Bored by
     beautiful prose that doesn't go anywhere.
   - **The Writer** — published author. Structure, beat placement,
     foreshadowing payoff, the gap between what a novel attempts and
     achieves. Highest compliment: "I forgot I was reading." Worst
     verdict: "I can see the outline."
   - **The First Reader** — thoughtful general reader. No craft
     terminology. Emotional honesty: "I didn't care about this part,"
     "I had to put the book down after this scene."

5. Each persona answers the same ten questions, JSON-formatted:
   `momentum_loss`, `earned_ending`, `cut_candidate`, `missing_scene`,
   `thinnest_character`, `best_scene`, `worst_scene`,
   `would_recommend`, `haunts_you`, `next_book`. Answers name specific
   chapter numbers and quote passages when possible.

   **When a custom rubric was parsed in step 2**, each persona also
   answers one extra free-text field per criterion: `custom_rubric:
   {criterion_text: persona_finding}`. The persona evaluates the
   whole book against the rule and names the chapters that violate
   it. Different personas often catch different violations — that's
   the value of running it through the panel rather than only
   `/autonovel:evaluate`.

6. After all four have responded, compute disagreements. For each of
   `momentum_loss`, `cut_candidate`, `thinnest_character`,
   `worst_scene`, extract any `Ch N` references. A chapter flagged by
   some personas but not others is a disagreement — record
   `{question, chapter, flagged_by, not_flagged}`.

7. Use `file_write` to save the full panel to
   `books/{book}/edit_logs/reader_panel.json`:
   ```json
   {
     "readers": {"editor": {...}, "genre_reader": {...}, ...},
     "disagreements": [{"question": "...", "chapter": N,
                        "flagged_by": [...], "not_flagged": [...]}],
     "custom_rubric": [{"criterion": "...",
                        "violations_per_reader": {"editor": ["Ch 3", "Ch 7"], ...}}],
     "timestamp": "..."
   }
   ```
   Omit the `custom_rubric` key when no rubric was parsed in step 2.

8. Print a one-screen summary: per-persona one-line takes, plus the
   disagreements section (the one the user actually needs to act on).
</workflow>

<acceptance>
- `books/{book}/edit_logs/reader_panel.json` exists.
- Contains a `readers` object with exactly four keys:
  `editor`, `genre_reader`, `writer`, `first_reader`.
- Each reader has answers to all ten questions (no null values).
- `disagreements` is a list (may be empty if all four agreed).
- When voice.md Part 3 contains at least one bullet criterion,
  `custom_rubric` is a list with one entry per criterion; each
  entry's `violations_per_reader` is a dict keyed by reader name
  (chapters they flagged for that rule, possibly empty).
</acceptance>
