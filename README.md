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

Verso can make the ground truth, a sample of line images with OCR drafts to
correct by hand, and it can measure the character error rate of Tesseract on
it. It can read a whole part into one text file, and join the words that are
broken by a hyphen at a line end.

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

### Measure the error rate

```powershell
verso cer groundtruth\part1 --report work\cer-part1.tsv
```

This reads each line image of the ground truth with Tesseract, and compares
the text with the hand transcription. It gives the character error rate (CER)
for all lines, and for the lines not marked UNCERTAIN, then the most frequent
errors, for example `s -> f`. The report has one row for each line, with both
texts. The `work` folder is in `.gitignore`.

The CER is the edit distance between the two texts, divided by the number of
characters of the transcription. The distances and the lengths of all lines
are added up before the division. Before the comparison, both texts get the
same normalisation: Unicode NFC, one space between words, and no space before
`, . : ; ? ! ) ]` or after `( [`. The rules do not record those spaces.

By default, each line first gets the f to s change of `verso read` (see
below), so the CER is that of the text that `verso read` writes. Give
`--no-long-s` to measure Tesseract alone. Nothing else is changed.

Each run first checks that every `.gt.txt` file holds exactly the text of its
row in `transcription.tsv`. A test does the same check on the committed part 1
ground truth.

### Read a part

```powershell
verso read ..\recto\out\part1
```

This reads every column image in the folder, line by line, and writes
`work\part1-lat.txt`. The text keeps the printed lines: one line of text for
each line of type. A marker line comes before each column:

    === p0013-verso-c1 ===

The label is also the name of the column image, so each part of the text can
be found again in recto's output. A page that recto could not do gets a
marker that says so. A line with no OCR text is written as `{?}`, and the
command lists each one, so that no line goes missing without a sign. Each
line gets the spacing normalisation of `verso cer`.

A part is about 19000 lines. One line takes about 0.09 s, so the columns are
read in parallel, by default one for each CPU. Give `--jobs` to use fewer.
On the laptop, a first run of part 2 (296 columns, 19539 lines) took 11
minutes with the default.
The text of each finished column is kept in `work\part1\lines-lat`. A run
that stops goes on from there when you start it again. To read every column
again, for example after a change to the reading, delete that folder.

The model is in the names of the cache folder and the text file, so the
output of two models stays apart.

A part can hold more than one work. Give `--first` and `--last` to read only
the page sides from one side to another, and `--dest` to give the text its
own file:

```powershell
verso read ..\recto\out\part3 --last p0036-verso
verso read ..\recto\out\part3 --first p0061-recto --dest work\part3-apoc-lat.txt
verso read ..\recto\out\part4
```

Volume 11 holds two commentaries. Super Iohannem fills parts 1 and 2 and
ends on part 3 p0036-verso, with "FINIS" across its two columns. Its
indexes follow. In Apocalypsim starts on part 3 p0061-recto with its own
title page, and it fills part 4, which ends with its index of Scripture
passages. Each side given must have a column image, so a blank side is
refused. The line finder gives no line for "FINIS" or for the heading
"INDEX" under it, so the text of part 3 ends with "Amen.".

A word that the printer broke with a hyphen at a line end is made whole on
the first line, and the hyphen is removed. Every other line break stays, so
each line of text still matches one line of type, except that its last word
can be whole. The join goes past column and page markers. If the rest of the
word was the only word of its line, that line is removed. One or two specks
after the hyphen, for example `coi- |` or `Areopagi--`, are removed too. A
break is not joined when the next line is `{?}`, when a page that recto could
not do comes between, or at the end of the text. Its hyphen then stays.

The cache keeps the lines as Tesseract read them, with the hyphens. The joins
are made each time the text is put together, so a change to them needs no new
OCR run. On part 1, 5523 words were joined and 84 lines were removed.

After the joins, each long s that Tesseract read as f is changed back to s.
The stock `lat` model reads nearly every long s as f: in part 1, "eft" occurs
1808 times and "est" once. Thus the text itself cannot show the correct
forms. The word list comes from the dictionary in the model that reads the
text. `combine_tessdata` and `dawg2wordlist` extract it at the start of each
run. They must be next to `tesseract.exe` or on PATH. The Windows installer
puts them next to `tesseract.exe`.

That dictionary holds many misreads too, for example "eft" and "nifi". Thus
a word changes if a form of it with one or more f changed to s is in the
list, and the form with the fewest changes is used. A word that touches a
hyphen or `&` is a part of a word, and it stays as read.

Some real f words have an s form in the list, for example Filius and the
name Silius, or fuit and the English word suit. Those words are in
`src\verso\longs_keep.txt`, and they stay as read. That file also holds
pairs where both forms are common Latin, for example fit and sit. Add a word
to it on a line of its own. Give `--no-long-s` to keep every f as read.

Known limits: a word with two long s, where the list holds a form with only
one of them changed, keeps one f ("scripfit"). A word with a second OCR
error keeps that error ("cft" becomes "cst"). On part 1, 14086 words are
changed.

## Measurements

All numbers are for the 99 part 1 ground truth lines, read with the stock
`lat` model on the development laptop (Windows, Tesseract 5.5.3). Every change
to the reading is judged against the last row.

| Reading | All 99 lines | 77 lines not UNCERTAIN |
|---|---|---|
| Mode 7 for each line | 21.03 % (937 of 4456) | 18.26 % (633 of 3466) |
| Mode 7, then mode 13 if empty | 17.93 % (799 of 4456) | 15.18 % (526 of 3466) |
| Same, then f to s with the model's word list | 16.65 % (742 of 4456) | 13.85 % (480 of 3466) |

Mode 7 gave no text for 5 lines. Three were clean lines, which mode 13 read.
The other two are lines where the other side of the leaf shows through, and
mode 13 gives noise for them. The docstring of `src\verso\tesseract.py` gives
the detail.

The most frequent error is the long s read as f: 116 times, in 252 letters s
of the transcription. That is about 2.6 points of CER. The other errors are
mostly single letters lost or changed by the damage of the scan, for example
a lost space (34), u read as a (19), a full stop read as a comma (18), and æ
read as e (17).

The f to s change takes the long s errors from 116 to 58, and it changes one
real f to s: "af-", where the hyphen was read as a full stop.

## Tests

```powershell
python -m pytest
```

## License

MIT. See [LICENSE](LICENSE).
