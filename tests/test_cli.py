"""Check that the command line starts and reports its version."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from verso import __version__
from verso.cli import main
from verso.manifest import MANIFEST_NAME


def test_help_runs() -> None:
    """Check that both help options print the help and exit with 0."""
    runner = CliRunner()
    for option in ("--help", "-h"):
        result = runner.invoke(main, [option])
        assert result.exit_code == 0, result.output
        assert "Usage:" in result.output


def test_version_matches_package() -> None:
    """Check that --version prints the version of the package."""
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0, result.output
    assert __version__ in result.output


def test_lines_names_an_unknown_column(tmp_path: Path) -> None:
    """Check that a label not in the manifest stops the run before any OCR."""
    (tmp_path / MANIFEST_NAME).write_text("", encoding="utf-8")
    result = CliRunner().invoke(main, ["lines", str(tmp_path), "--column", "p9999-verso-c1"])
    assert result.exit_code != 0
    assert "p9999-verso-c1" in result.output
