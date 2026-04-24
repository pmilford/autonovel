---
name: autonovel:research
description: Research a real-world topic with live web search and write sourced notes into shared/research/notes/.
argument-hint: "\"<topic>\""
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - web_search
  - web_fetch
reads:
  - project.yaml
  - shared/research/sources.yaml
  - shared/sources.bib
  - shared/world.md
  - shared/research/notes/{topic}.md
writes:
  - shared/research/notes/{topic}.md
  - shared/sources.bib
context_mode: series
---

<purpose>
Investigate `<topic>` against live web sources and produce a research
notes file the drafting and canon layers can trust. The output is a
markdown document at `shared/research/notes/<slug>.md` with an explicit
`## Sources` block (citations in BibTeX shortname form), a
`## Candidate Canon Entries` block, and uncertainty hedges where the web
record is thin. This command is the research-layer equivalent of a
writer walking into a special-collections library: it must cite, and it
must flag when it is guessing.

Design rules:
- The URLs in `shared/research/sources.yaml` marked `weight: primary`
  are mandatory stops. The command MUST call `web_fetch` on every
  primary URL before drafting notes. Secondary URLs are optional but
  strongly preferred.
- Additional sources come from `web_search` queries scoped to the
  topic. Prefer authoritative domains (`.edu`, `.gov`, `.org`,
  university presses, Britannica, national library archives) over
  general-web results.
- Every factual claim in the notes needs a citation. Citations use the
  BibTeX shortname format: `[shortname]`. New shortnames are appended
  to `shared/sources.bib`.
- Anything not recoverable from sources is marked `Speculative`,
  `Uncertain`, or `Needs verification` — never silently asserted.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. The topic is a free-form quoted string, e.g.
   `"Venetian apothecaries 1520"`. Anything not quoted is still
   accepted as a single topic. Missing topic → stop with a one-line
   reminder: `usage: /autonovel:research "<topic>"`.

2. Slugify the topic (lowercase, non-alphanumerics → `-`, collapse
   repeats, trim). Example: `"Venetian apothecaries 1520"` →
   `venetian-apothecaries-1520`. That slug is `<slug>` for the rest
   of the workflow. The notes file is
   `shared/research/notes/<slug>.md` (what `{topic}.md` resolves to
   at runtime).

3. Use `file_read` on `project.yaml` to pull `period.start`,
   `period.end`, `period.region`, and `genre`. These pin the research
   window — when a web result predates or postdates the series
   period, flag it.

4. Use `file_read` on `shared/research/sources.yaml`. Collect every
   entry whose `weight` is `primary` into `primary_urls`; collect
   `secondary` into `secondary_urls`. If the file is missing or
   empty, proceed with an empty list.

5. Use `file_read` on `shared/world.md` and any existing
   `shared/research/notes/{topic}.md`. The world bible pins what has
   already been canonized; a pre-existing notes file is the prior
   run we are extending, not overwriting.

6. Call `web_fetch` on every URL in `primary_urls`. Record the
   rendered page's key facts verbatim with the source URL attached.
   If a primary URL fails to fetch (404, network error), keep the
   attempt and add a `Needs verification` note in the draft — do
   not silently skip it.

7. Call `web_search` at least twice with queries derived from the
   topic and the series period. Examples for a 1520 Venetian topic:
   `"Venetian apothecaries 1520 Rialto"`,
   `"speziale guild Venice sixteenth century"`. Record at least
   four additional candidate sources from the search results, then
   `web_fetch` the two or three most authoritative.

8. Synthesize. Draft notes under the following section skeleton.
   Concrete over abstract. Every H2 section names its sources with
   bracketed shortnames that also exist in `shared/sources.bib`.

   ```
   # Research — <topic>

   Updated <UTC-date>. Period: <start>-<end> <region>.

   ## Summary
   (Two to four paragraphs. The facts a chapter writer can lean on
   without second-guessing. Every claim carries [shortname].)

   ## Material detail
   (Physical specifics — tools, ingredients, clothing, buildings,
   smells, money, scale. This is what rescues a chapter from
   generic period flavour.)

   ## People and institutions
   (Named offices, guilds, families. Dates where known.)

   ## Uncertainties
   - Speculative: ...
   - Uncertain: ...
   - Needs verification: ...

   ## Candidate Canon Entries
   - <fact> [shortname]
   - <fact> [shortname]

   ## Sources
   - [shortname1] Short attribution line + URL + weight
     (primary/secondary/search).
   - [shortname2] ...
   ```

   Minimum bars for the smoke test to pass:
   - At least two distinct `[shortname]` citations appear in the
     body.
   - At least one URL listed under `## Sources` matches a primary
     URL from `shared/research/sources.yaml`.
   - The `## Candidate Canon Entries` section has at least one entry,
     with a shortname.
   - At least one of the words `Speculative`, `Uncertain`, or
     `Needs verification` appears.

9. Use `file_write` to save the notes to
   `shared/research/notes/{topic}.md` (with `{topic}` replaced by
   the slug). Overwrite any prior version.

10. Use `file_write` to append new shortname entries to
    `shared/sources.bib`. Every shortname cited in step 8 must be
    resolvable from `shared/sources.bib` — append if missing, leave
    alone if already there. Skip this step if every citation was
    already in the bib.
</workflow>

<acceptance>
- `shared/research/notes/<slug>.md` exists and begins with a
  `# Research — <topic>` heading.
- The file contains a `## Sources` section with ≥ 2 distinct
  `[shortname]` citations.
- At least one `url:` from the `primary` entries of
  `shared/research/sources.yaml` is present as a substring of the
  notes file.
- At least one of `Speculative`, `Uncertain`, or
  `Needs verification` appears in the file.
- A `## Candidate Canon Entries` section exists.
- Every `[shortname]` cited in the notes resolves to an entry in
  `shared/sources.bib`.
</acceptance>
