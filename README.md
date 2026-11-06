# verso

[![tests](https://github.com/chriscruz06/verso/actions/workflows/test.yml/badge.svg)](https://github.com/chriscruz06/verso/actions/workflows/test.yml)

Reads the column images of an early-modern Latin book into text.

Verso is the second stage of an OCR pipeline for a translation of Albertus
Magnus, *Super Iohannem*, in the Jammy edition (Lyons, 1651, *Operum Tomus
Undecimus*). The first stage, [recto](https://github.com/chriscruz06/recto),
cuts the scanned volume into one clean image for each text column, and writes a
manifest that says where each image came from. Verso reads those images with
Tesseract and writes the Latin text in the reading order of the book. The
translation is a separate, later stage.

## Status

This is the start of the project. The command line runs, but it has no
subcommands yet.

## Install

Python 3.11 or newer. Recto must be cloned beside verso, because verso uses
its line finder. Install recto from that clone, so that a change to recto is
seen here at once.

```powershell
git clone https://github.com/chriscruz06/verso.git
cd verso
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ..\recto
pip install -e ".[dev]"
verso --help
```

## Tests

```powershell
python -m pytest
```

## License

MIT. See [LICENSE](LICENSE).
