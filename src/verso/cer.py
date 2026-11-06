"""Measure the character error rate of an OCR reader against the ground truth.

The character error rate is the edit distance between the OCR text and the
hand transcription, divided by the length of the hand transcription. Each
insertion, deletion and substitution of one character costs 1. Over many
lines, the distances and the lengths are added up before the division, so a
long line weighs more than a short one.

Both texts are normalised first, in the same way:

    Unicode NFC, so that a letter with a combining tilde and the same letter
    with its tilde built in are one character.

    Spacing. Runs of white space become one space, and the spaces before
    , . : ; ? ! ) ] and after ( [ are removed. The transcription rules do not
    record these spaces, because their width cannot be read well. Tesseract
    gives them, so without this step every printed space before a colon would
    count as an error that the rules chose not to measure.

Nothing else is changed. A long s that Tesseract reads as f counts as an
error, because the rules write it as s.

The alignment also counts each kind of error, for example s read as f. These
counts show what a better reader must fix.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from verso.transcription import Entry

_SPACE = re.compile(r"\s+")
_BEFORE = re.compile(r" ([,.:;?!)\]])")
_AFTER = re.compile(r"([(\[]) ")


def normalise(text: str) -> str:
    """Normalise a line for comparison.

    Args:
        text: A line of text.

    Returns:
        The line in NFC, with the spacing normalised as the module docstring
        says.
    """
    text = unicodedata.normalize("NFC", text)
    text = _SPACE.sub(" ", text).strip()
    text = _BEFORE.sub(r"\1", text)
    return _AFTER.sub(r"\1", text)


def align(truth: str, read: str) -> list[tuple[str, str]]:
    """Align two strings with the fewest edits.

    Args:
        truth: The correct text.
        read: The text to measure.

    Returns:
        One pair for each step of the alignment: (a, a) for a match, (a, b)
        for a substitution, (a, "") for a deletion of a, and ("", b) for an
        insertion of b. The number of pairs that are not matches is the edit
        distance.
    """
    rows, cols = len(truth) + 1, len(read) + 1
    cost = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        cost[i][0] = i
    for j in range(cols):
        cost[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            same = truth[i - 1] == read[j - 1]
            cost[i][j] = min(
                cost[i - 1][j - 1] + (0 if same else 1),
                cost[i - 1][j] + 1,
                cost[i][j - 1] + 1,
            )

    # Walk back from the end. A tie prefers the diagonal, so a wrong letter
    # is counted as one substitution and not as a deletion and an insertion.
    pairs = []
    i, j = len(truth), len(read)
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            step = 0 if truth[i - 1] == read[j - 1] else 1
            if cost[i][j] == cost[i - 1][j - 1] + step:
                pairs.append((truth[i - 1], read[j - 1]))
                i, j = i - 1, j - 1
                continue
        if i > 0 and cost[i][j] == cost[i - 1][j] + 1:
            pairs.append((truth[i - 1], ""))
            i -= 1
        else:
            pairs.append(("", read[j - 1]))
            j -= 1
    pairs.reverse()
    return pairs


@dataclass(frozen=True)
class LineScore:
    """The result for one line."""

    entry: Entry
    truth: str
    """The normalised transcription."""

    read: str
    """The normalised OCR text."""

    errors: tuple[tuple[str, str], ...]
    """The pairs of the alignment that are not matches."""

    @property
    def distance(self) -> int:
        """The edit distance."""
        return len(self.errors)

    @property
    def length(self) -> int:
        """The number of characters of the normalised transcription."""
        return len(self.truth)


@dataclass
class Total:
    """The sum over a set of lines."""

    lines: int = 0
    distance: int = 0
    length: int = 0
    errors: Counter = field(default_factory=Counter)

    @property
    def rate(self) -> float | None:
        """The character error rate, or None if there are no characters."""
        return self.distance / self.length if self.length else None


def score_line(entry: Entry, read: str) -> LineScore:
    """Score one line.

    Args:
        entry: The row of the record.
        read: The text that the OCR reader gave for the line image.

    Returns:
        The score of the line.
    """
    truth, text = normalise(entry.text), normalise(read)
    errors = tuple(pair for pair in align(truth, text) if pair[0] != pair[1])
    return LineScore(entry=entry, truth=truth, read=text, errors=errors)


def total(scores: Iterable[LineScore], keep: Callable[[LineScore], bool]) -> Total:
    """Add up the scores of the lines that a test keeps.

    Args:
        scores: The line scores.
        keep: The test.

    Returns:
        The sum.
    """
    result = Total()
    for score in scores:
        if not keep(score):
            continue
        result.lines += 1
        result.distance += score.distance
        result.length += score.length
        result.errors.update(score.errors)
    return result
