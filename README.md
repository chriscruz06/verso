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

Verso can make the ground truth: a sample of line images with OCR drafts to
correct by hand. Measuring the error rate and reading a whole part are the
next steps.

## Install

Python 3.11 or newer, and Tesseract on PATH with the `lat` language data.

Verso uses recto's line finder, and pip gets recto from GitHub. If recto is
cloned beside verso, install that clone last, so that a change to recto is
seen here at once. If you install verso again later, install recto again after
it, because pip can replace the clone with the copy from GitHub.

```powershell
git clone https://github.com/chriscruz06/verso.git
cd verso
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pip install -e ..\recto
verso --help
```

## Use

### Make the ground truth

Accuracy can only be measured against lines that a person has checked.
`verso lines` cuts lines from some columns of a recto output folder, and
writes each line as an image and a text file with Tesseract's draft:

```powershell
verso lines ..\recto\out\part1 --column p0013-verso-c1 --column p0020-recto-c2 --column p0030-verso-c2 --column p0045-recto-c1 --column p0060-verso-c1
```

This takes 20 lines from each column, at even spacing, and writes them to
`groundtruth\part1`:

    p0013-verso-c1-l039.png      the line image
    p0013-verso-c1-l039.gt.txt   the draft, to correct by hand

The names follow the Tesseract training format. Open each image, and make its
text file say what is printed. A pair that is already there is never written
again, so a second run does not change corrected lines. The ground truth comes
from part 1 only. Parts 2 to 4 are kept to check each change.

The lines are found with recto's `band_column`. Tesseract's own line finder
was tried first, and on the bold, fused lines of p13 verso it gave overlapping
boxes and empty lines.

### Transcription rules

These rules set what a correct line is. A change to them changes every error
rate measured against the ground truth.

- Write the long s (ſ) as s.
- Keep æ and œ as printed. Where the printer set a and e apart, write ae.
- Keep u, v, i and j as printed. Do not change them to the modern use.
- Keep accents as printed, for example à, è and ë.
- Keep abbreviations as printed. Write a tilde or a bar over a letter as that
  letter with a tilde: ã, ẽ, ĩ, õ, ũ, ñ. If there is no such letter, write
  the letter and then the combining tilde, U+0303. Write the ampersand as &.
- Write the ligatures ct and st as two letters.
- Keep the punctuation as printed, and keep the hyphen at the end of a line.
- Keep square brackets as printed. The edition puts them around the words of
  the Gospel that the commentary takes up.
- Put one space between words. Put no space before , . : ; ? ! ) or ], and
  none after ( or [. The printer often put a space before a colon, but the
  width of a space cannot be read well, so it is not recorded.
- Do not mark italic or large type.
- Do not write marks in the margin, specks, or bits of the lines above and
  below.
- If an image holds no text, or holds two lines, or holds a sign that these
  rules do not cover, delete its two files.

### The record of the transcription

Each folder of ground truth holds `transcription.tsv`, the hand transcription
as it was made, with four columns: `file`, `text`, `status` and `note`. The
`.gt.txt` files hold the same text, one line each. The status of a line is
one of these:

| Status | Meaning |
|---|---|
| OK | A clean read. |
| BRACKET | A clean read of a line with square brackets. |
| UNCERTAIN | The best reading. The note names the doubtful part. |
| DELETE | The line holds a sign that the rules do not cover. Its image and its `.gt.txt` file are deleted. The row stays, so the record is complete. |

The part 1 lines were read from the images before any OCR output was looked
at, so the drafts did not bias them.

## Tests

```powershell
python -m pytest
```

## License

MIT. See [LICENSE](LICENSE).
