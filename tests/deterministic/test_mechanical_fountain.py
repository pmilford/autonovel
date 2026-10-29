"""Tier-1 tests for `autonovel mechanical fountain-check` (film pipeline F1).

The checker is what `/autonovel:screenplay` relies on to know a script is
well formed: headings a breakdown can use, every speaker in the book's
cast or listed as a role (no new named people), a scene line under every
heading, and a length in eighths of a page. It must agree with the
renderer (screenplain) about what is a heading and what is a title page,
or a script that "passes" prints wrong.
"""

from __future__ import annotations

import builtins
import json
from pathlib import Path

import pytest

from autonovel.mechanical import fountain as fm
from autonovel.mechanical.__main__ import main as mech_main


CAST = """# Cast

- **Ana** (ch 1) is one trait so far.

### Ana Marsh — the heroine (invented)

### Zuan Vianello — the steward of the Fondaco, the dark mentor (invented)

## Ensemble

| in the record | in the prose |
|---|---|
| Barbara Bäsinger | "his mother" |

### Bit parts
- **The ferryman**, who never takes coins.
- **The innkeeper at the Flute**: "It likes Germans."
"""

GOOD = """Title: The Crossing
Credit: Sequence 1
Roles:
    BOATMAN
First minute: S0101 — the river at night, one face, no lip-sync

EXT. RIVER - NIGHT

= S0101 | ch_01:5-7 | dry -> wet

ANA MARSH (20s) stands at the edge of the black water. The FERRYMAN poles in.

ANA
Take me across.

FERRYMAN
(shaking his head)
Not tonight.

INT. FERRY HUT - DAWN

= S0102 | invented (carries ch_01:6) | alone -> found

Ana wakes on a bench. Vianello watches her from the door.

BOATMAN (O.S.)
Up.

VIANELLO
You slept in your coat.
"""


def _book(tmp_path: Path, script: str = GOOD, cast: str = CAST) -> tuple[Path, Path]:
    series = tmp_path / "s"
    book = series / "books" / "b"
    (book / "chapters").mkdir(parents=True)
    (book / "film" / "screenplay").mkdir(parents=True)
    (series / "shared").mkdir(parents=True)
    (series / "shared" / "characters.md").write_text("# Characters\n", encoding="utf-8")
    (book / "cast.md").write_text(cast, encoding="utf-8")
    (book / "chapters" / "ch_01.md").write_text(
        "---\nchapter: 1\n---\n\nAna stood by the river.\nThe ferryman came.\nShe slept.\n",
        encoding="utf-8")
    path = book / "film" / "screenplay" / "seq_01.fountain"
    path.write_text(script, encoding="utf-8")
    return book, path


# ------------------------------------------------------------------ parsing

def test_parse_elements_title_page_and_line_numbers() -> None:
    text = "Title: T\nRoles:\n    CARTER\n    INNKEEPER\n\n[[a note\nover two lines]]\n\nINT. HALL - NIGHT\n\n= S0101 | ch_02:1-3 | a -> b\n\nAction here.\n\nJAKOB (V.O.)\n(quietly)\nEvery coin.\n"
    title, els, problems = fm.parse(text)
    assert title == {"Title": ["T"], "Roles": ["CARTER", "INNKEEPER"]}
    assert not problems
    kinds = [(e.kind, e.line) for e in els]
    # The note's two lines are blanked, not removed: the heading keeps line 9.
    assert ("heading", 9) in kinds
    assert [e.kind for e in els] == ["heading", "synopsis", "action", "cue", "paren", "dialogue"]
    assert fm.cue_name("JAKOB (V.O.)") == ("JAKOB", ["V.O."])


def test_title_page_follows_screenplain_rules() -> None:
    """A key with an inline value takes no indented lines (screenplain then
    treats the whole block as body text); the checker must say so."""
    title, _, problems = fm.parse("Title: T\nRoles: CARTER\n    INNKEEPER\n\nINT. A - DAY\n\nx\n")
    assert title == {}
    assert problems and "title page was not read" in problems[0]


def test_heading_forms() -> None:
    assert fm.split_heading("INT. FONDACO - LONG HALL - NIGHT") == ("INT.", "FONDACO - LONG HALL", "NIGHT", "")
    assert fm.split_heading("int/ext barge – dusk #12#") == ("INT./EXT.", "barge", "DUSK", "12")
    assert fm.split_heading("EXT. RIVER") == ("EXT.", "RIVER", "", "")
    _, els, _ = fm.parse(".THE HIGH PASS\n\nWind.\n")
    assert els[0].kind == "heading" and els[0].forced


def test_heading_without_blank_line_after_is_an_error(tmp_path: Path) -> None:
    script = GOOD.replace("EXT. RIVER - NIGHT\n\n= S0101", "EXT. RIVER - NIGHT\n= S0101")
    _, path = _book(tmp_path, script)
    rep = fm.check(path)
    assert any("no blank line after it" in e for e in rep.errors)


def test_heading_checks(tmp_path: Path) -> None:
    script = GOOD.replace("EXT. RIVER - NIGHT", "EXT. RIVER").replace(
        "INT. FERRY HUT - DAWN", "INT. FERRY HUT - TEATIME")
    _, path = _book(tmp_path, script)
    rep = fm.check(path)
    assert any("no time of day" in e for e in rep.errors)
    assert any("TEATIME" in w for w in rep.warnings)


# ------------------------------------------------------------------ speakers

def test_speakers_matched_against_cast_and_roles(tmp_path: Path) -> None:
    _, path = _book(tmp_path)
    rep = fm.check(path)
    assert rep.ok, rep.errors
    sp = rep.speakers
    assert sp["ANA"]["status"] == "cast" and "Ana Marsh" in sp["ANA"]["match"]
    assert sp["VIANELLO"]["status"] == "cast"
    assert sp["FERRYMAN"]["status"] == "cast"          # a bit part in cast.md
    assert sp["BOATMAN"]["status"] == "role"           # listed under Roles:


def test_unknown_speaker_is_an_error(tmp_path: Path) -> None:
    _, path = _book(tmp_path, GOOD + "\nHANS\nWho's there?\n")
    rep = fm.check(path)
    assert not rep.ok
    assert any("HANS speaks but is neither in the cast" in e for e in rep.errors)


def test_table_row_names_count_as_cast(tmp_path: Path) -> None:
    _, path = _book(tmp_path, GOOD + "\nBARBARA (V.O.)\nEvery coin.\n")
    rep = fm.check(path)
    assert rep.speakers["BARBARA"]["status"] == "cast"
    assert rep.voice_over_lines == 1


def test_a_table_cell_listing_several_people_is_split(tmp_path: Path) -> None:
    cast = CAST + "\n| Kaspar the weaver, Melem, Utz the carter | each by what he is |\n"
    _, path = _book(tmp_path, GOOD + "\nCARTER\nHold the mule.\n", cast)
    rep = fm.check(path)
    assert rep.speakers["CARTER"]["match"].startswith("Utz the carter")


def test_long_title_page_line_is_flagged(tmp_path: Path) -> None:
    script = GOOD.replace("Credit: Sequence 1",
                          "Credit: Sequence 1 of a screenplay adapted from a very long novel indeed")
    _, path = _book(tmp_path, script)
    rep = fm.check(path)
    assert any("title page Credit" in a and "55" in a for a in rep.advisories)


def test_one_person_two_cues_warns(tmp_path: Path) -> None:
    _, path = _book(tmp_path, GOOD + "\nZUAN VIANELLO\nDeclare your coin.\n")
    rep = fm.check(path)
    assert any("one person, two cues" in w and "ZUAN VIANELLO" in w for w in rep.warnings)


def test_no_cast_file_leaves_speakers_unchecked(tmp_path: Path) -> None:
    path = tmp_path / "loose.fountain"
    path.write_text(GOOD, encoding="utf-8")
    rep = fm.check(path)
    assert rep.ok
    assert rep.speakers["ANA"]["status"] == "unchecked"
    assert any("no cast.md found" in w for w in rep.warnings)


def test_scene_characters_include_named_but_silent(tmp_path: Path) -> None:
    _, path = _book(tmp_path)
    rep = fm.check(path)
    hut = rep.scenes[1]
    assert hut.speaking == ["BOATMAN", "VIANELLO"]
    assert "ANA" in hut.characters      # in the action, speaks elsewhere


# ------------------------------------------------------------------ scene lines

def test_scene_lines_parsed(tmp_path: Path) -> None:
    _, path = _book(tmp_path)
    rep = fm.check(path)
    river, hut = rep.scenes
    assert river.id == "S0101" and river.turn == "dry -> wet"
    assert river.source == [{"chapter": 1, "from": 5, "to": 7}]
    assert hut.source[0]["invented"] is True
    assert rep.first_minute["scene"] == "S0101"
    assert "one face" in rep.first_minute["why"]


def test_scene_line_problems(tmp_path: Path) -> None:
    script = (GOOD.replace("= S0102 | invented (carries ch_01:6) | alone -> found",
                           "= S0101 | chapter two | alone and found")
              .replace("First minute: S0101", "First minute: S0199"))
    _, path = _book(tmp_path, script)
    rep = fm.check(path)
    assert any("repeats" in e for e in rep.errors)
    assert any("not understood" in e for e in rep.errors)
    assert any("doesn't name a before and an after" in w for w in rep.warnings)
    assert any("S0199" in e for e in rep.errors)


def test_missing_scene_line_when_others_have_one(tmp_path: Path) -> None:
    script = GOOD.replace("= S0102 | invented (carries ch_01:6) | alone -> found\n\n", "")
    _, path = _book(tmp_path, script)
    rep = fm.check(path)
    assert any("has no scene line" in e for e in rep.errors)


# ------------------------------------------------------------------ length

def test_eighths_labels() -> None:
    assert fm.eighths_label(4) == "4/8"       # never reduced to 1/2
    assert fm.eighths_label(11) == "1 3/8"
    assert fm.eighths_label(16) == "2"


def test_page_count_in_eighths(tmp_path: Path) -> None:
    # One heading, then a page's worth of one-line action paragraphs:
    # 2 lines per paragraph (blank + text). 27 paragraphs + heading = 56 lines.
    body = "INT. ROOM - DAY\n\n" + "\n".join(f"Beat {i}.\n" for i in range(27))
    path = tmp_path / "p.fountain"
    path.write_text(body, encoding="utf-8")
    rep = fm.check(path)
    assert rep.page_lines == 56
    assert rep.scenes[0].eighths == 8
    # A tiny scene is never less than an eighth.
    path.write_text("INT. A - DAY\n\nx\n", encoding="utf-8")
    assert fm.check(path).scenes[0].eighths == 1


def test_wrapping_uses_the_standard_widths() -> None:
    long_line = "word " * 30          # 150 characters
    assert fm.wrapped_lines(long_line, fm.WIDTHS["action"]) == 3
    assert fm.wrapped_lines(long_line, fm.WIDTHS["dialogue"]) == 5
    assert fm.wrapped_lines("*bold* and _under_", 61) == 1


def test_advisories(tmp_path: Path) -> None:
    action = " ".join(["The boy counts the coins again."] * 12)
    speech = " ".join(["I will pay you by Christmas."] * 8)
    script = GOOD + f"\nINT. HALL - NIGHT\n\n= S0103 | ch_01:7 | a -> b\n\n{action}\n\nANGLE ON the knife.\n\nANA\n{speech}\n"
    _, path = _book(tmp_path, script)
    rep = fm.check(path)
    assert any("action block of" in a for a in rep.advisories)
    assert any("ANGLE ON" in a for a in rep.advisories)
    assert any("ANA speaks" in a for a in rep.advisories)


# ------------------------------------------------------------------ scenes.json

def test_scenes_json_written_and_stamped(tmp_path: Path) -> None:
    book, path = _book(tmp_path)
    rep = fm.run(path, do_export=False, stamp=True)
    data = json.loads((book / "film" / "scenes.json").read_text(encoding="utf-8"))
    seq = data["sequences"]["01"]
    assert seq["scenes"] == ["S0101", "S0102"]
    assert seq["source_lines"] == {"ch_01": [5, 7]}
    assert seq["first_minute"]["scene"] == "S0101"
    assert set(seq["adapted_from"]) == {"ch_01"}
    ids = [s["id"] for s in data["scenes"]]
    assert ids == ["S0101", "S0102"]
    river = data["scenes"][0]
    assert river["slugline"] == "EXT. RIVER - NIGHT"
    assert river["speaking"] == ["ANA", "FERRYMAN"]
    assert river["eighths"] >= 1 and river["length"]
    assert rep.scenes_json.endswith("scenes.json")


def test_scenes_json_keeps_other_sequences_and_extra_keys(tmp_path: Path) -> None:
    book, path = _book(tmp_path)
    sj = book / "film" / "scenes.json"
    sj.write_text(json.dumps({
        "schema": "autonovel-film-scenes/1",
        "sequences": {"02": {"file": "screenplay/seq_02.fountain"},
                      "01": {"note": "kept"}},
        "scenes": [{"id": "S0201", "seq": "02"}, {"id": "S0109", "seq": "01"}],
    }), encoding="utf-8")
    fm.run(path, do_export=False, stamp=True)
    data = json.loads(sj.read_text(encoding="utf-8"))
    assert "02" in data["sequences"] and data["sequences"]["01"]["note"] == "kept"
    ids = [s["id"] for s in data["scenes"]]
    assert ids == ["S0101", "S0102", "S0201"]      # the old S0109 replaced


def test_changed_chapter_flags_the_sequence(tmp_path: Path) -> None:
    book, path = _book(tmp_path)
    fm.run(path, do_export=False, stamp=True)
    ch = book / "chapters" / "ch_01.md"
    ch.write_text(ch.read_text(encoding="utf-8") + "A new line.\n", encoding="utf-8")
    rep = fm.run(path, do_export=False)
    assert any("ch_01 has changed since this sequence was adapted" in w for w in rep.warnings)
    rep = fm.run(path, do_export=False, stamp=True)
    assert not any("has changed" in w for w in rep.warnings)


# ------------------------------------------------------------------ exports

def test_export_degrades_without_screenplain(tmp_path: Path, monkeypatch) -> None:
    real_import = builtins.__import__

    def no_screenplain(name, *args, **kwargs):
        if name.startswith("screenplain"):
            raise ImportError("No module named 'screenplain'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_screenplain)
    book, path = _book(tmp_path)
    rep = fm.run(path)
    assert rep.ok
    assert "autonovel[export]" in rep.exports["skipped"]
    assert not (book / "film" / "export").exists()


def _have_screenplain() -> bool:
    try:
        import screenplain.parsers.fountain  # noqa: F401
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _have_screenplain(),
                    reason="screenplain not installed; pip install autonovel[export]")
def test_export_pdf_and_fdx(tmp_path: Path) -> None:
    book, path = _book(tmp_path)
    rep = fm.run(path)
    pdf = book / "film" / "export" / "seq_01.pdf"
    fdx = book / "film" / "export" / "seq_01.fdx"
    assert pdf.is_file() and fdx.is_file()
    assert rep.exports["pdf_pages"] == 2          # title page + one page
    check = rep.exports["fdx_check"]
    assert check["ok"]
    assert check["paragraphs"]["Scene Heading"] == 2
    assert check["paragraphs"]["Character"] == 4


@pytest.mark.skipif(not _have_screenplain(),
                    reason="screenplain not installed; pip install autonovel[export]")
def test_pdf_keeps_each_speech_whole_and_restores_screenplain(tmp_path: Path) -> None:
    """A speech must not break across a page with no (MORE): the export
    keeps each speech together, and leaves screenplain as it found it."""
    from screenplain.export import pdf as sp_pdf
    before = sp_pdf.add_dialog
    before_para = sp_pdf.add_paragraph
    speeches = "\n".join(f"ANA\n(quietly)\nLine {i} of a long night.\n" for i in range(40))
    _, path = _book(tmp_path, GOOD + "\nINT. HALL - NIGHT\n\n= S0103 | ch_01:7 | a -> b\n\n" + speeches)
    seen: list = []
    real_to_pdf = sp_pdf.to_pdf

    def spy(screenplay, out, **kw):
        seen.append((sp_pdf.add_dialog, sp_pdf.add_paragraph))
        return real_to_pdf(screenplay, out, **kw)

    sp_pdf.to_pdf = spy
    try:
        rep = fm.run(path)
    finally:
        sp_pdf.to_pdf = real_to_pdf
    assert rep.exports["pdf_pages"] >= 3
    try:
        import pypdf  # noqa: F401
        assert rep.exports["pdf_page_breaks"] == "ok"   # no stranded heading
    except ImportError:
        pass
    assert seen and seen[0][0] is not before        # whole speeches
    assert seen[0][1] is not before_para            # and whole paragraphs
    assert sp_pdf.add_dialog is before and sp_pdf.add_paragraph is before_para  # put back


# ------------------------------------------------------------------ CLI

def test_cli_exit_codes_and_formats(tmp_path: Path, capsys) -> None:
    _, path = _book(tmp_path)
    assert mech_main(["fountain-check", str(path), "--no-export", "--no-scenes"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and out["length"] and len(out["scenes"]) == 2
    assert mech_main(["fountain-check", str(path), "--no-export", "--no-scenes",
                      "--format", "markdown"]) == 0
    assert "| S0101 |" in capsys.readouterr().out
    path.write_text(GOOD + "\nHANS\nHello.\n", encoding="utf-8")
    assert mech_main(["fountain-check", str(path), "--no-export", "--no-scenes"]) == 1
    assert mech_main(["fountain-check", str(tmp_path / "missing.fountain")]) == 2
