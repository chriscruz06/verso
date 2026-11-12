"""Check the f to s change, its word list and its keep list."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from verso import longs as module
from verso.longs import (
    LongS,
    LongSError,
    default_keep,
    extract_words,
    find_tool,
    parse_keep,
    tessdata_dir,
)


def change(words: set[str], keep: set[str] = frozenset()) -> LongS:
    """Make the change from small word lists.

    Args:
        words: The model words.
        keep: The words that stay as read.

    Returns:
        The change.
    """
    return LongS(words=frozenset(words), keep=frozenset(keep))


def test_long_s_read_as_f_is_changed() -> None:
    """Check a simple word, and that the case of the letter stays."""
    fix = change({"est", "sicut"})
    assert fix.word("eft") == "est"
    assert fix.word("Ficut") == "Sicut"


def test_a_word_with_no_s_form_in_the_list_stays() -> None:
    """Check that a real f word stays if the list has no s form of it."""
    assert change({"est"}).word("fecit") == "fecit"


def test_the_form_with_the_fewest_changes_is_used() -> None:
    """Check the order when the list holds a form with half its f changed."""
    fix = change({"scripfit", "scripsit"})
    assert fix.word("fcripfit") == "scripfit"


def test_a_word_in_the_keep_list_stays() -> None:
    """Check that a kept word stays in any case."""
    fix = change({"silius"}, keep={"filius"})
    assert fix.word("Filius") == "Filius"


def test_a_word_with_too_many_f_stays() -> None:
    """Check the limit on the number of forms."""
    word = "f" * (module.MAX_F + 1)
    assert change({"s" * len(word)}).word(word) == word


def test_a_line_skips_parts_of_words_and_counts_changes() -> None:
    """Check that words next to a hyphen or & stay, and the count."""
    fix = change({"as", "asse", "est", "sed"})
    text, changed = fix.line("af- affe&um eft, fed")
    assert text == "af- affe&um est, sed"
    assert changed == 2


def test_parse_keep_ignores_comments_and_empty_lines() -> None:
    """Check the format of the keep list."""
    assert parse_keep("# note\n\n Filius \nfuit\n") == {"filius", "fuit"}


def test_the_package_keep_list_loads() -> None:
    """Check that the keep list is part of the package and has its words."""
    keep = default_keep()
    assert {"filius", "fuit", "fit", "foris", "fata"} <= keep
    assert not any(word.startswith("#") for word in keep)


def test_find_tool_prefers_the_folder_of_tesseract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check the search order for a training program."""
    tesseract = tmp_path / "tesseract.exe"
    tool = tmp_path / "dawg2wordlist.exe"
    tool.write_text("")
    monkeypatch.setattr(module.shutil, "which", lambda name: "/elsewhere/" + name)
    assert find_tool(str(tesseract), "dawg2wordlist") == str(tool)
    assert find_tool(str(tesseract), "combine_tessdata") == "/elsewhere/combine_tessdata"
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    with pytest.raises(LongSError):
        find_tool(str(tesseract), "combine_tessdata")


def fake_programs(
    monkeypatch: pytest.MonkeyPatch, tessdata: Path, *, fail: str = ""
) -> None:
    """Replace tesseract and its training programs with stand ins.

    Args:
        monkeypatch: The pytest fixture.
        tessdata: The folder that tesseract --list-langs names.
        fail: The name of a program that fails, or empty for none.
    """

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Do what each program does to the files.

        Args:
            command: The program and its arguments.
            **kwargs: The options of subprocess.run, not used.

        Returns:
            The result.
        """
        name = Path(command[0]).name
        if name == fail:
            return subprocess.CompletedProcess(command, 1, "", "it broke")
        if command[1:] == ["--list-langs"]:
            out = f'List of available languages in "{tessdata}/" (1):\nlat\n'
            return subprocess.CompletedProcess(command, 0, out, "")
        if name == "combine_tessdata":
            prefix = command[3]
            Path(prefix + "lstm-unicharset").write_text("")
            Path(prefix + "lstm-word-dawg").write_text("")
        if name == "dawg2wordlist":
            Path(command[3]).write_text("Eft\nest\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(module.subprocess, "run", run)
    monkeypatch.setattr(module.shutil, "which", lambda name: name)


def test_tessdata_dir_is_read_from_list_langs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check the folder in the output of tesseract --list-langs."""
    fake_programs(monkeypatch, tmp_path / "td")
    assert tessdata_dir("tesseract") == tmp_path / "td"


def test_extract_words_gives_the_words_in_lower_case(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check the steps of the extraction with stand in programs."""
    tessdata = tmp_path / "td"
    tessdata.mkdir()
    (tessdata / "lat.traineddata").write_text("")
    work = tmp_path / "work"
    work.mkdir()
    fake_programs(monkeypatch, tessdata)
    assert extract_words("tesseract", "lat", work) == {"eft", "est"}


def test_extract_words_needs_the_model_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check the error for a language with no model file."""
    fake_programs(monkeypatch, tmp_path)
    with pytest.raises(LongSError, match="no model file"):
        extract_words("tesseract", "lat", tmp_path)


def test_a_failed_program_is_an_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check that the output of a failed program is in the error."""
    (tmp_path / "lat.traineddata").write_text("")
    fake_programs(monkeypatch, tmp_path, fail="dawg2wordlist")
    with pytest.raises(LongSError, match="it broke"):
        extract_words("tesseract", "lat", tmp_path)


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="needs Tesseract")
def test_the_installed_lat_model_gives_its_words(tmp_path: Path) -> None:
    """Check the extraction with the real programs, where they are installed."""
    tesseract = shutil.which("tesseract")
    assert tesseract is not None
    try:
        model = tessdata_dir(tesseract) / "lat.traineddata"
    except LongSError as exc:
        pytest.skip(str(exc))
    if not model.is_file():
        pytest.skip("the lat model is not installed")
    words = extract_words(tesseract, "lat", tmp_path)
    assert {"est", "sicut", "nisi"} <= words
