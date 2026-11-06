"""verso: OCR of recto's column images into Latin text.

Recto cuts a scanned volume into one clean image for each text column, and
writes a manifest that says where each image came from. Verso reads those
images with Tesseract and writes the text in the reading order of the book.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
