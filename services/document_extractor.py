"""
Document Extractor
===================
Extracts raw text from PDF and DOCX files.

**This module is designed to be replaceable.**
In the future, swap the local extraction logic with an API call:

    class APIDocumentExtractor(DocumentExtractor):
        def extract(self, file_bytes, file_name):
            resp = requests.post("https://your-api/extract", files={"file": file_bytes})
            return resp.json()["text"]

The rest of the application only depends on the ``extract()`` and
``extract_with_metadata()`` interfaces.
"""

import io
import os
import sys
from typing import Any

import fitz  # PyMuPDF
from docx import Document as DocxDocument

# Configure Tesseract path for Windows
if sys.platform.startswith("win"):
    tesseract_path = r"C:\Program Files\Tesseract-OCR"
    if os.path.exists(tesseract_path):
        os.environ["PATH"] += os.pathsep + tesseract_path
        if "TESSDATA_PREFIX" not in os.environ:
            os.environ["TESSDATA_PREFIX"] = os.path.join(tesseract_path, "tessdata")


class DocumentExtractor:
    """
    Extract raw text content from PDF or DOCX documents.

    This class provides a clean interface for text extraction that can be
    replaced with an API-backed implementation in the future. Simply pass
    the document bytes to ``extract()`` and receive the full text back.

    Supported formats:
        - PDF  (.pdf)  — via PyMuPDF
        - DOCX (.docx) — via python-docx
    """

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def extract(self, file_bytes: bytes, file_name: str) -> str:
        """
        Extract the full text content of a document.

        Parameters
        ----------
        file_bytes : bytes
            Raw bytes of the uploaded file.
        file_name : str
            Original file name (used to determine format by extension).

        Returns
        -------
        str
            The extracted plain-text content of the document.

        Raises
        ------
        ValueError
            If the file format is not supported.
        """
        extension = self._get_extension(file_name)

        if extension == ".pdf":
            return self._extract_pdf(file_bytes)
        elif extension == ".docx":
            return self._extract_docx(file_bytes)
        else:
            raise ValueError(
                f"Unsupported file format: '{extension}'. "
                f"Please upload a .pdf or .docx file."
            )

    def extract_with_metadata(self, file_bytes: bytes, file_name: str) -> dict[str, Any]:
        """
        Extract text along with document metadata.

        Parameters
        ----------
        file_bytes : bytes
            Raw bytes of the uploaded file.
        file_name : str
            Original file name.

        Returns
        -------
        dict
            Keys: ``text``, ``file_name``, ``file_size_kb``, ``page_count``,
            ``format``, ``metadata`` (format-specific metadata dict).
        """
        extension = self._get_extension(file_name)

        if extension == ".pdf":
            return self._extract_pdf_with_metadata(file_bytes, file_name)
        elif extension == ".docx":
            return self._extract_docx_with_metadata(file_bytes, file_name)
        else:
            raise ValueError(
                f"Unsupported file format: '{extension}'. "
                f"Please upload a .pdf or .docx file."
            )

    # ------------------------------------------------------------------ #
    #  PDF extraction (PyMuPDF)                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_pdf(file_bytes: bytes) -> str:
        """Extract text from all pages of a PDF, falling back to OCR if scanned."""
        text_parts: list[str] = []
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                blocks = page.get_text("blocks")
                page_text = ""
                if blocks:
                    # type 0 is text (as opposed to image blocks)
                    block_texts = [b[4].strip() for b in blocks if b[6] == 0]
                    # Join blocks with double newlines to ensure ParagraphSplitter sees them as separate
                    page_text = "\n\n".join(b for b in block_texts if b)
                
                # If no text found, try OCR
                if not page_text:
                    try:
                        page_text = page.get_textpage_ocr(flags=0, language="eng", dpi=300).extractText().strip()
                    except Exception as e:
                        print(f"OCR failed for page: {e}")

                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_pdf_with_metadata(file_bytes: bytes, file_name: str) -> dict[str, Any]:
        """Extract text and metadata from a PDF."""
        text_parts: list[str] = []
        first_heading = ""

        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            page_count = len(doc)
            pdf_metadata = doc.metadata or {}
            for page in doc:
                page_text = page.get_text("text").strip()
                
                # If no text found, try OCR
                if not page_text:
                    try:
                        page_text = page.get_textpage_ocr(flags=0, language="eng", dpi=300).extractText().strip()
                    except Exception as e:
                        print(f"OCR failed for page: {e}")

                if page_text:
                    if not first_heading:
                        # Grab the very first non-empty line as a fallback heading
                        first_line = page_text.split("\n")[0].strip()
                        if first_line:
                            first_heading = first_line
                    text_parts.append(page_text)

        return {
            "text": "\n\n".join(text_parts),
            "file_name": file_name,
            "file_size_kb": round(len(file_bytes) / 1024, 1),
            "page_count": page_count,
            "format": "PDF",
            "metadata": {
                "title": pdf_metadata.get("title", ""),
                "author": pdf_metadata.get("author", ""),
                "subject": pdf_metadata.get("subject", ""),
                "creator": pdf_metadata.get("creator", ""),
                "first_heading": first_heading,
            },
        }

    # ------------------------------------------------------------------ #
    #  DOCX extraction (python-docx)                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_docx(file_bytes: bytes) -> str:
        """Extract text from all paragraphs and tables of a DOCX."""
        doc = DocxDocument(io.BytesIO(file_bytes))
        parts: list[str] = []

        # Extract paragraphs
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                parts.append(text)

        # Extract text from tables (row by row)
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    parts.append(row_text)

        return "\n\n".join(parts)

    @staticmethod
    def _extract_docx_with_metadata(file_bytes: bytes, file_name: str) -> dict[str, Any]:
        """Extract text and metadata from a DOCX."""
        doc = DocxDocument(io.BytesIO(file_bytes))
        parts: list[str] = []
        first_heading = ""

        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                # If it's a heading style, or just the very first text we see
                is_heading_style = para.style and ("Heading" in para.style.name or "Title" in para.style.name)
                if not first_heading and is_heading_style:
                    first_heading = text
                elif not first_heading and len(parts) == 0:
                    first_heading = text
                parts.append(text)

        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    parts.append(row_text)

        core = doc.core_properties
        return {
            "text": "\n\n".join(parts),
            "file_name": file_name,
            "file_size_kb": round(len(file_bytes) / 1024, 1),
            "page_count": len(doc.sections),  # approximate via sections
            "format": "DOCX",
            "metadata": {
                "title": core.title or "",
                "author": core.author or "",
                "subject": core.subject or "",
                "created": str(core.created) if core.created else "",
                "first_heading": first_heading,
            },
        }

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_extension(file_name: str) -> str:
        """Return the lowercased file extension including the dot."""
        if "." in file_name:
            return "." + file_name.rsplit(".", 1)[-1].lower()
        return ""
