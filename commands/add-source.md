---
name: autonovel:add-source
description: Add a URL or DOI to the research bibliography and sources.yaml; optionally re-run research.
argument-hint: "<url-or-doi> [--shortname <key>] [--weight primary|secondary] [--title \"<title>\"] [--research <topic>]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - web_fetch
reads:
  - shared/sources.bib
  - shared/research/sources.yaml
writes:
  - shared/sources.bib
  - shared/research/sources.yaml
context_mode: series
---

<purpose>
Sidequest: register a new research source. Appends a BibTeX entry to
`shared/sources.bib` (so later notes can cite it with `[shortname]`)
and an entry to `shared/research/sources.yaml` (so
`/autonovel:research` will `web_fetch` it on future runs).

If `--weight primary` is passed, the URL becomes a mandatory stop for
every subsequent research run. Secondary URLs are advisory.

Optionally (`--research <topic>`) chains into
`/autonovel:research "<topic>"` after the source is registered, so a
single invocation both adds the source and re-researches the affected
notes file. (This command does NOT invoke the research command
itself — per the sidequest dispatcher rule, it prints the suggested
follow-up command.)
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: positional `<url-or-doi>`. Optional:
   `--shortname <key>` (derive one from the domain if absent —
   `britannica.com` → `britannica-<slug>`), `--weight primary |
   secondary` (default `secondary`),
   `--title "<title>"` (if absent, fetch the page and pull
   `<title>`), `--research <topic>` (suggest, do not invoke).

2. Normalize. If the argument begins with `10.` treat it as a DOI
   and expand to `https://doi.org/<doi>`. Otherwise treat it as a
   URL; reject anything that does not start with `http://` or
   `https://`.

3. Use `file_read` on `shared/sources.bib` and
   `shared/research/sources.yaml`. If `<url>` is already present in
   either file, stop with a one-line reminder — duplicate adds are
   a no-op, not an error, but the user should know.

4. If `--title` was not supplied, use `web_fetch` to pull the page
   and extract the `<title>`. Fall back to the URL's domain if the
   page has no title or the fetch fails.

5. Use `file_write` to append a BibTeX entry to
   `shared/sources.bib`:

       @misc{<shortname>,
         title   = {<title>},
         url     = {<url>},
         urldate = {<UTC-date>},
         note    = {Weight: <primary|secondary>},
       }

   Keep the rest of `shared/sources.bib` verbatim.

6. Use `file_write` to append an entry to
   `shared/research/sources.yaml` under the top-level `sources:`
   list:

       - url: <url>
         title: <title>
         weight: <primary|secondary>

   Preserve existing entries and file header comments verbatim.

7. If `--research <topic>` was passed, do NOT run the research
   command — print the suggested follow-up verbatim:

       Next: /autonovel:research "<topic>"

   Otherwise print a short confirmation (shortname, weight, URL).
</workflow>

<acceptance>
- `shared/sources.bib` contains a new `@misc{...}` entry keyed by
  the chosen shortname.
- `shared/research/sources.yaml` contains a new `sources:` entry
  whose `url` matches the argument.
- No research notes under `shared/research/notes/` are modified by
  this command (re-research is the user's separate step).
- If the URL was already present, nothing was written.
</acceptance>
