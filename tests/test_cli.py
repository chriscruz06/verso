"""Check that the command line starts and reports its version."""

from __future__ import annotations

from click.testing import CliRunner

from verso import __version__
from verso.cli import main


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
