"""Check the normalisation, the alignment and the sums of the error rate."""

from __future__ import annotations

from pathlib import Path

import pytest

from verso.cer import align, normalise, score_line, total
from verso.transcription import Entry


def entry(text: str, status: str = "OK") -> Entry:
    """Make a row of the record without files.

    Args:
        text: The transcription.
        status: The status.

    Returns:
        The row.
    """
    return Entry(image=Path("x-l001.png"), text=text, status=status, note="")


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("ex ore : nisi", "ex ore: nisi"),
        ("intellectus , sicut", "intellectus, sicut"),
        ("( vt dicit Aug. )", "(vt dicit Aug.)"),
        ("[ Tu quis es ? ]", "[Tu quis es?]"),
        ("  Nec   diceret \t", "Nec diceret"),
    ],
)
def test_spacing_that_the_rules_do_not_record_is_removed(raw: str, clean: str) -> None:
    """Check that only the spacing named in the rules changes.

    Args:
        raw: Text with printed or OCR spacing.
        clean: The same text as the rules write it.
    """
    assert normalise(raw) == clean


def test_combining_tilde_equals_the_built_in_letter() -> None:
    """Check that a tilde typed as a combining mark is the same character."""
    assert normalise("ã") == normalise("ã")
    assert len(normalise("ã")) == 1


def test_letters_are_not_changed() -> None:
    """Check that f for long s and e for ae stay errors."""
    assert normalise("effe fic") == "effe fic"
    assert normalise("cæli") == "cæli"


def test_alignment_counts_each_kind_of_edit() -> None:
    """Check one substitution, one deletion and one insertion."""
    errors = [p for p in align("esse", "effe") if p[0] != p[1]]
    assert errors == [("s", "f"), ("s", "f")]
    errors = [p for p in align("dicit", "dict") if p[0] != p[1]]
    assert errors == [("i", "")]
    errors = [p for p in align("est", "eft,") if p[0] != p[1]]
    assert errors == [("s", "f"), ("", ",")]


def test_alignment_of_empty_text() -> None:
    """Check that an empty read costs one error for each character."""
    assert len([p for p in align("vitam.", "") if p[0] != p[1]]) == 6
    assert align("", "") == []


def test_line_score() -> None:
    """Check the distance and the length of one line after normalisation."""
    score = score_line(entry("nisi ab ore dicentis"), "nifi ab orc  dicentis")
    assert score.length == len("nisi ab ore dicentis")
    assert score.distance == 2
    assert sorted(score.errors) == [("e", "c"), ("s", "f")]


def test_total_weighs_long_lines_more() -> None:
    """Check that the sums are added before the division."""
    short = score_line(entry("ab"), "xb")
    long = score_line(entry("abcdefghij"), "abcdefghij")
    every = total([short, long], lambda s: True)
    assert every.distance == 1 and every.length == 12
    assert every.rate == pytest.approx(1 / 12)


def test_total_can_leave_out_uncertain_lines() -> None:
    """Check the filter that the cer command uses."""
    sure = score_line(entry("est"), "eft")
    doubt = score_line(entry("cum", "UNCERTAIN"), "eum")
    certain = total([sure, doubt], lambda s: s.entry.status != "UNCERTAIN")
    assert certain.lines == 1 and certain.errors == {("s", "f"): 1}
    assert total([], lambda s: True).rate is None
