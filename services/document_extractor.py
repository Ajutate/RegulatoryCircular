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
import tempfile
from typing import Any

from docx import Document as DocxDocument
# Configure Tesseract path across OSes
def _configure_tesseract():
    from dotenv import load_dotenv
    load_dotenv()
    
    # 1. User-configured override from .env
    env_tesseract = os.environ.get("TESSERACT_PATH")
    if env_tesseract and os.path.exists(env_tesseract):
        if env_tesseract not in os.environ.get("PATH", ""):
            os.environ["PATH"] += os.pathsep + env_tesseract
        if "TESSDATA_PREFIX" not in os.environ:
            tess_data = os.path.join(env_tesseract, "tessdata")
            if os.path.exists(tess_data):
                os.environ["TESSDATA_PREFIX"] = tess_data
        
        # Still apply HF fix for Windows if necessary
        if sys.platform.startswith("win"):
            os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
            os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
        return

    # 2. Auto-discovery fallback
    if sys.platform.startswith("win"):
        # Windows
        win_paths = [r"C:\Program Files\Tesseract-OCR", r"C:\Program Files (x86)\Tesseract-OCR"]
        for p in win_paths:
            if os.path.exists(p):
                os.environ["PATH"] += os.pathsep + p
                if "TESSDATA_PREFIX" not in os.environ:
                    tess_data = os.path.join(p, "tessdata")
                    if os.path.exists(tess_data):
                        os.environ["TESSDATA_PREFIX"] = tess_data
                break
                
        # Fix HuggingFace Hub symlink issue on Windows without Developer Mode
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    else:
        # macOS / Linux
        if "TESSDATA_PREFIX" not in os.environ:
            unix_tessdata_paths = [
                "/usr/share/tesseract-ocr/5/tessdata",
                "/usr/share/tesseract-ocr/4.00/tessdata",
                "/usr/share/tessdata",
                "/opt/homebrew/share/tessdata",
                "/usr/local/share/tessdata"
            ]
            for p in unix_tessdata_paths:
                if os.path.exists(p):
                    os.environ["TESSDATA_PREFIX"] = p
                    break

_configure_tesseract()

# We import DocumentConverter from docling
from docling.document_converter import DocumentConverter


class DocumentExtractor:
    """
    Extract raw text content from PDF or DOCX documents.

    This class provides a clean interface for text extraction that can be
    replaced with an API-backed implementation in the future. Simply pass
    the document bytes to ``extract()`` and receive the full text back.

    Supported formats:
        - PDF  (.pdf)  — via IBM Docling
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
    #  PDF extraction (IBM Docling)                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_pdf(file_bytes: bytes) -> str:
        """
        Extract text from a PDF using IBM Docling.
        Returns beautifully structured Markdown.
        """
        # Save to a temporary file since Docling's converter is safest with a physical file path
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name

        try:
            converter = DocumentConverter()
            result = converter.convert(tmp_path)
            # Export the structured document to Markdown
            markdown_text = result.document.export_to_markdown()
            return markdown_text
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @staticmethod
    def _extract_pdf_with_metadata(file_bytes: bytes, file_name: str) -> dict[str, Any]:
        """Extract text and metadata from PDF using Docling."""
        # For simplicity, we just return the text and basic metadata
        text = DocumentExtractor._extract_pdf(file_bytes)
        
        return {
            "text": text,
            "file_name": file_name,
            "file_size_kb": round(len(file_bytes) / 1024, 2),
            "page_count": 0, # Docling doesn't give a simple page count out of the box in the markdown output
            "format": "pdf",
            "metadata": {"extracted_by": "docling"}
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
