"""Change the long s that Tesseract reads as f back to s.

The book prints s in two forms. The round s is at the end of a word, and
Tesseract reads it correctly. The long s is at the start and in the middle of
a word, and the stock lat model reads it as f nearly every time. In part 1,
"eft" occurs 1808 times and "est" occurs once. Thus the text cannot give the
correct forms, and a word list must give them.

The word list comes from the dictionary in the Tesseract model that reads the
text. combine_tessdata unpacks the model, and dawg2wordlist writes the words.
This takes about 0.2 s, so it is done again on each run, and the list always
agrees with the model.

That list was made partly from old printed books, so it also holds the
misreads, for example "eft", "nifi" and "Chrift". Thus a word in the list is
not proof that its f is a real f. The rule is: if a form of the word with one
or more f changed to s is in the list, that form replaces the word. If more
than one form is in the list, the form with the fewest changes is used,
because the list also holds forms with half of their long s misread.

Some real f words have an s form in the list too, for example Filius and
Silius, or fuit and the English suit. The keep list names those words, and
they stay as read. It also names pairs where both forms are common Latin, for
example fit and sit, because one word alone cannot show which is printed.

On the 99 part 1 ground truth lines (Tesseract 5.5.3), this rule took the
character error rate from 17.93 to 16.65 percent, and s read as f from 116
to 58 times.
"""

from __future__ import annotations

import itertools
import re
import shutil
import subprocess
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

WORD = re.compile(r"(?<![&\-\w])[^\W\d_]+(?![&\-\w])")
"""A word of letters only, with no letter, digit, hyphen or & next to it.

A word that touches a hyphen is a part of a word broken at a line end. The
hyphen joins come before this step, so such a part was not joined, and its
other part is not known. A word that touches & is often a part of a word too,
because Tesseract reads the ct ligature as &, for example "affe&um"."""

MAX_F = 4
"""Words with more f than this stay as read. The number of forms to look up
doubles with each f, and no word in part 1 needs more than 4."""

KEEP_FILE = "longs_keep.txt"
"""The keep list in the package, one word on each line."""


class LongSError(RuntimeError):
    """The word list cannot be made from the Tesseract model."""


def find_tool(tesseract: str, name: str) -> str:
    """Find a Tesseract training program.

    Args:
        tesseract: The path of the tesseract program.
        name: The name of the program, without a file extension.

    Returns:
        The path of the program.

    Raises:
        LongSError: If the program is not found.
    """
    # The Windows installer puts the programs in the folder of tesseract.exe,
    # but Linux packages can put them in another folder on PATH.
    sibling = Path(tesseract).with_name(name + Path(tesseract).suffix)
    if sibling.is_file():
        return str(sibling)
    found = shutil.which(name)
    if found is None:
        raise LongSError(f"{name} not found next to {tesseract} or on PATH")
    return found


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a Tesseract program, and stop if it fails.

    Args:
        command: The program and its arguments.

    Returns:
        The result.

    Raises:
        LongSError: If the program gives an exit status that is not 0.
    """
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr + result.stdout).strip()
        raise LongSError(f"{Path(command[0]).name} failed: {message}")
    return result


def tessdata_dir(tesseract: str) -> Path:
    """Find the folder that holds the Tesseract models.

    Args:
        tesseract: The path of the tesseract program.

    Returns:
        The folder that tesseract --list-langs names.

    Raises:
        LongSError: If tesseract fails or its output has no folder.
    """
    # The list names the folder that tesseract really uses, which includes
    # the effect of TESSDATA_PREFIX.
    result = _run([tesseract, "--list-langs"])
    found = re.search(r'languages in "([^"]+)"', result.stdout + result.stderr)
    if found is None:
        raise LongSError("tesseract --list-langs did not name its tessdata folder")
    return Path(found.group(1))


def extract_words(tesseract: str, lang: str, workdir: Path) -> frozenset[str]:
    """Get the dictionary words of a Tesseract model.

    Args:
        tesseract: The path of the tesseract program.
        lang: The Tesseract language, for example "lat".
        workdir: A folder for the unpacked model.

    Returns:
        The words, in lower case.

    Raises:
        LongSError: If a program is missing or fails, or if the model has no
            word dictionary.
    """
    model = tessdata_dir(tesseract) / f"{lang}.traineddata"
    if not model.is_file():
        raise LongSError(f"no model file {model}")
    prefix = workdir / f"{lang}."
    _run([find_tool(tesseract, "combine_tessdata"), "-u", str(model), str(prefix)])
    unicharset = workdir / f"{lang}.lstm-unicharset"
    dawg = workdir / f"{lang}.lstm-word-dawg"
    if not (unicharset.is_file() and dawg.is_file()):
        raise LongSError(f"{model} has no LSTM word dictionary")
    out = workdir / f"{lang}-words.txt"
    _run([find_tool(tesseract, "dawg2wordlist"), str(unicharset), str(dawg), str(out)])
    return frozenset(out.read_text(encoding="utf-8").lower().split())


def parse_keep(text: str) -> frozenset[str]:
    """Read a keep list.

    Args:
        text: The list. Each line holds one word. A line that starts with #
            is a comment. Empty lines are ignored.

    Returns:
        The words, in lower case.
    """
    words = (line.strip().lower() for line in text.splitlines())
    return frozenset(w for w in words if w and not w.startswith("#"))


def default_keep() -> frozenset[str]:
    """Read the keep list that is part of the package.

    Returns:
        The words, in lower case.
    """
    return parse_keep(files("verso").joinpath(KEEP_FILE).read_text(encoding="utf-8"))


def _s_forms(word: str) -> list[str]:
    """Give each form of a word with one or more f changed to s.

    Args:
        word: The word.

    Returns:
        The forms, the fewest changes first. Empty if the word has no f or
        more than MAX_F.
    """
    places = [i for i, char in enumerate(word) if char in "fF"]
    if len(places) > MAX_F:
        return []
    forms = []
    for count in range(1, len(places) + 1):
        for chosen in itertools.combinations(places, count):
            letters = list(word)
            for i in chosen:
                letters[i] = "s" if word[i] == "f" else "S"
            forms.append("".join(letters))
    return forms


@dataclass(frozen=True)
class LongS:
    """The f to s change, with its word list and keep list."""

    words: frozenset[str]
    """The words of the model, in lower case."""

    keep: frozenset[str]
    """The words that stay as read, in lower case."""

    def word(self, word: str) -> str:
        """Change one word.

        Args:
            word: A word of letters only.

        Returns:
            The first form in the word list, or the word if no form is in it
            or if the word is in the keep list.
        """
        if word.lower() in self.keep:
            return word
        for form in _s_forms(word):
            if form.lower() in self.words:
                return form
        return word

    def line(self, text: str) -> tuple[str, int]:
        """Change each word of one line.

        Args:
            text: The line.

        Returns:
            The new line, and the number of words changed.
        """
        changed = 0

        def one(match: re.Match[str]) -> str:
            """Change the word of one match, and count it.

            Args:
                match: The match of WORD.

            Returns:
                The new word.
            """
            nonlocal changed
            new = self.word(match.group(0))
            changed += new != match.group(0)
            return new

        return WORD.sub(one, text), changed
