"""Join the words that the printer broke with a hyphen at a line end.

In part 1, 5087 of the 18445 lines end with a letter and a hyphen, and 65 of
the 288 columns end in the middle of a word. The rest of the word is the first
word of the next line of text, which can be after a column marker, on the
next column or the next page.

The rest of the word moves up to the end of the broken line, and the hyphen
is removed. Every other line break stays where the printer put it, so each
line of text still matches one line of type, except that its last word can be
whole. If the rest of the word was the only word of its line, that line is
then empty, and it is removed. In part 1 this happens 80 times, mostly at the
end of a paragraph, for example "mun-" and "dum.".

A broken line is a line that ends with a letter and a hyphen. One or two
marks after the hyphen are taken as specks and removed: in part 1, 436 broken
lines end as "coi- |", "fan-." or "Areopagi--". A hyphen after a space or a
digit is not a break.

The rest of the word is the first run of characters up to a space, whatever
its first character is. OCR often reads the first letters of that word as
other signs, for example "&ualium" for "ctualium", because the ct ligature is
read as &. Those signs still belong to the word.

A break is not joined if the next line of text is a line with no OCR text, if
a page that recto could not do comes between, or if there is no next line.
The hyphen then stays, so the break can be seen.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

BREAK = re.compile(r"([^\W\d_])-\s*[^\w\s]{0,2}$")
"""A letter, the hyphen, and up to two marks after it, at the end of a line.
The second group of the class removes digits and the underscore from \\w, so
that the first character is a letter."""


@dataclass
class Joins:
    """What join_hyphens did."""

    joined: int = 0
    """Words made whole."""

    removed: int = 0
    """Lines that became empty and were removed."""

    kept: int = 0
    """Breaks that were not joined. Their hyphen stays."""


def join_hyphens(
    lines: list[str],
    *,
    is_marker: Callable[[str], bool],
    stops: Callable[[str], bool],
) -> tuple[list[str], Joins]:
    """Join the words broken at line ends.

    Args:
        lines: The text, one printed line or one marker line each.
        is_marker: True for a marker line. A join goes past a marker.
        stops: True for a line that a join must not reach or go past, for
            example a line with no OCR text, or the marker of a page that was
            not read.

    Returns:
        The new lines, and what was done.
    """
    out = list(lines)
    joins = Joins()
    gone: set[int] = set()
    for index in range(len(out)):
        if index in gone or is_marker(out[index]):
            continue
        # A loop, because the moved word can itself end with a break if it
        # was the only word of its line.
        while (match := BREAK.search(out[index])) is not None:
            following = _next_text(out, index, gone, is_marker, stops)
            if following is None:
                joins.kept += 1
                break
            head = out[index][: match.start(1) + 1]
            tail, _, rest = out[following].partition(" ")
            out[index] = head + tail
            joins.joined += 1
            if rest:
                out[following] = rest
                break
            gone.add(following)
            joins.removed += 1
    return [line for number, line in enumerate(out) if number not in gone], joins


def _next_text(
    lines: list[str],
    index: int,
    gone: set[int],
    is_marker: Callable[[str], bool],
    stops: Callable[[str], bool],
) -> int | None:
    """Find the line of text after a broken line.

    Args:
        lines: The text.
        index: The broken line.
        gone: Lines already removed.
        is_marker: True for a marker line.
        stops: True for a line that a join must not reach or go past.

    Returns:
        The index of the next line of text, or None if there is no line to
        join with.
    """
    for number in range(index + 1, len(lines)):
        line = lines[number]
        if number in gone:
            continue
        if stops(line) or not line.strip():
            return None
        if is_marker(line):
            continue
        return number
    return None
