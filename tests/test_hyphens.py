"""Check the joining of words broken by a hyphen at a line end.

The examples come from the part 1 text of verso read.
"""

from __future__ import annotations

from verso.hyphens import join_hyphens
from verso.reader import EMPTY_LINE, is_gap, is_marker, marker


def join(lines: list[str]) -> tuple[list[str], object]:
    """Join with the marker tests that verso read uses.

    Args:
        lines: The text.

    Returns:
        The new lines and what was done.
    """
    return join_hyphens(
        lines,
        is_marker=is_marker,
        stops=lambda line: line == EMPTY_LINE or is_gap(line),
    )


def test_rest_of_word_moves_up() -> None:
    """Check that the hyphen goes and the other line breaks stay."""
    out, joins = join(
        [
            "Secundum autem omnes expofitores idem in-",
            "zendizur.fcilicer, quod ficu natum ex carne cortu-",
            "prioni vitij fubie&a",
        ]
    )
    assert out == [
        "Secundum autem omnes expofitores idem inzendizur.fcilicer,",
        "quod ficu natum ex carne cortuprioni",
        "vitij fubie&a",
    ]
    assert joins.joined == 2 and joins.removed == 0


def test_join_goes_past_a_column_marker() -> None:
    """Check a word broken at the end of a column."""
    out, _ = join(
        [
            marker("p0013-recto-c1"),
            "& Deus dicuntur effe n principio:quia dicis Phi-",
            marker("p0013-recto-c2"),
            "lofoplius, quod silhil dt in feiyfo",
        ]
    )
    assert out == [
        marker("p0013-recto-c1"),
        "& Deus dicuntur effe n principio:quia dicis Philofoplius,",
        marker("p0013-recto-c2"),
        "quod silhil dt in feiyfo",
    ]


def test_specks_after_the_hyphen_are_removed() -> None:
    """Check the marks that part 1 shows after a hyphen."""
    for broken in ("habitabit in coi- |", "habitabit in coi--", "habitabit in coi-."):
        out, joins = join([broken, "pore tuo"])
        assert out == ["habitabit in coipore", "tuo"], broken
        assert joins.joined == 1


def test_line_of_one_word_is_removed() -> None:
    """Check the end of a paragraph, where the rest of the word is the line."""
    out, joins = join(["venientem in hunc mun-", "dum.", "Et vita erat"])
    assert out == ["venientem in hunc mundum.", "Et vita erat"]
    assert joins.removed == 1


def test_a_word_broken_twice_is_joined_twice() -> None:
    """Check that a moved word that ends with a break is joined again."""
    out, joins = join(["ab-", "solu-", "tionem dedit"])
    assert out == ["absolutionem", "dedit"]
    assert joins.joined == 2 and joins.removed == 1


def test_first_sign_of_the_rest_need_not_be_a_letter() -> None:
    """Check that the ct ligature read as & stays with its word."""
    out, _ = join(["porem celefium & intellc-", "&ualium gaudiorum"])
    assert out == ["porem celefium & intellc&ualium", "gaudiorum"]


def test_hyphens_that_are_not_breaks_stay() -> None:
    """Check a hyphen after a space or a digit, and a hyphen inside a line."""
    lines = ["Gratia sm affetius -", "Psalm. 16-", "quan-tum est", "ultima"]
    out, joins = join(lines)
    assert out == lines
    assert joins.joined == 0


def test_breaks_that_cannot_be_joined_keep_the_hyphen() -> None:
    """Check an empty OCR line, a missing page, and the end of the text."""
    gap = marker("p0011 not read by recto")
    cases = [
        ["idem in-", EMPTY_LINE, "tendizur"],
        ["idem in-", gap, "tendizur"],
        ["idem in-"],
    ]
    for lines in cases:
        out, joins = join(lines)
        assert out == lines
        assert joins.kept == 1 and joins.joined == 0
