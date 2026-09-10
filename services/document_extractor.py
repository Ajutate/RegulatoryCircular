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
from typing import Any

import pymupdf                          # PyMuPDF — modern import (fitz is deprecated)
from docx import Document as DocxDocument


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
            The extracted plain-text content of the document in Markdown format.

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
        with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                blocks = page.get_text("blocks", sort=True)
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
        text = DocumentExtractor._extract_pdf(file_bytes)
        
        first_heading = ""
        if text:
            first_line = text.split("\n")[0].strip()
            if first_line:
                first_heading = first_line

        with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
            page_count = len(doc)
            pdf_metadata = doc.metadata or {}

        return {
            "text": text,
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
        """Extract text from all paragraphs of a DOCX file."""
        doc = DocxDocument(io.BytesIO(file_bytes))
        # Keep empty paragraphs to preserve spacing (useful for chunking)
        paragraphs = [para.text for para in doc.paragraphs]
        return "\n".join(paragraphs)

    @staticmethod
    def _extract_docx_with_metadata(file_bytes: bytes, file_name: str) -> dict[str, Any]:
        """Extract text and metadata from DOCX file."""
        doc = DocxDocument(io.BytesIO(file_bytes))
        paragraphs = [para.text for para in doc.paragraphs]
        text = "\n".join(paragraphs)

        core_props = doc.core_properties
        metadata = {
            "author": core_props.author,
            "created": core_props.created.isoformat() if core_props.created else None,
            "modified": core_props.modified.isoformat() if core_props.modified else None,
            "title": core_props.title,
        }

        return {
            "text": text,
            "file_name": file_name,
            "file_size_kb": round(len(file_bytes) / 1024, 2),
            "page_count": None,  # Not applicable for DOCX natively
            "format": "docx",
            "metadata": metadata,
        }

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_extension(file_name: str) -> str:
        """Safely extract and lower-case the file extension."""
        _, ext = os.path.splitext(file_name)
        return ext.lower()
