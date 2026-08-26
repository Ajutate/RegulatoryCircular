"""
Paragraph Splitter
===================
Splits raw extracted text into meaningful regulatory paragraphs.

Strategy (using Docling Markdown):
  - Docling exports clean Markdown.
  - Paragraphs are separated by double newlines (\n\n).
  - List items (bullets/numbers) might be separated by single newlines.
  - We will treat each list item and each blank-line-separated block as a separate paragraph.
  - Noise (page numbers, standalone "Confidential", etc.) is filtered out.
"""

import re
import html


class ParagraphSplitter:
    """
    Split raw document text into a list of meaningful paragraphs.

    Takes advantage of Markdown formatting provided by Docling.
    """

    # Minimum character length to consider a block a valid paragraph
    MIN_PARAGRAPH_LENGTH = 15

    # Patterns for content that should be filtered out
    NOISE_PATTERNS = [
        re.compile(r"^\s*page\s*\d+\s*(of\s*\d+)?\s*$", re.IGNORECASE),
        re.compile(r"^\s*-\s*\d+\s*-\s*$"),
        re.compile(r"^\s*\d+\s*$"),
        re.compile(r"^\s*confidential\s*$", re.IGNORECASE),
        re.compile(r"^\s*draft\s*$", re.IGNORECASE),
    ]
    
    # Markdown list items start with -, *, +, or digits followed by a dot
    LIST_PATTERN = re.compile(r"^\s*([-*+]|\d+\.)\s+")

    def split(self, text: str) -> list[str]:
        """
        Split Markdown text into a list of cleaned paragraphs.

        Parameters
        ----------
        text : str
            The full extracted text of the document (Markdown formatted).

        Returns
        -------
        list[str]
            List of paragraph strings, each containing meaningful content.
        """
        if not text or not text.strip():
            return []

        # Step 0: Unescape HTML entities (e.g., &amp; -> &)
        text = html.unescape(text)

        # Step 1: Normalise line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Step 2: Split into individual lines
        raw_lines = text.split("\n")

        # Step 3: Group lines into paragraphs
        paragraphs: list[str] = []
        current_para_lines: list[str] = []

        for line in raw_lines:
            stripped = line.strip()

            # Blank line → flush current paragraph
            if not stripped:
                if current_para_lines:
                    paragraphs.append(" ".join(current_para_lines))
                    current_para_lines = []
                continue

            # Markdown List Item → flush previous paragraph, start new one
            if self.LIST_PATTERN.match(line): # using original line to preserve indent logic if needed, but stripped works too
                if current_para_lines:
                    paragraphs.append(" ".join(current_para_lines))
                    current_para_lines = []
                # Remove the markdown bullet point syntax for cleaner review text, or keep it?
                # Usually it's good to keep it so the user sees it's a list item.
                current_para_lines.append(stripped)
                continue
                
            # Markdown header
            if line.startswith("#"):
                if current_para_lines:
                    paragraphs.append(" ".join(current_para_lines))
                    current_para_lines = []
                current_para_lines.append(stripped)
                continue

            # Regular line → append to current paragraph
            current_para_lines.append(stripped)

        # Flush remaining buffer
        if current_para_lines:
            paragraphs.append(" ".join(current_para_lines))

        # Step 4: Filter noise (page numbers, headers, footers, table of contents)
        filtered = [p for p in paragraphs if not self._is_noise(p)]

        # Step 5: Final filter — remove anything still too short, but keep headers
        result = [p for p in filtered if len(p) >= self.MIN_PARAGRAPH_LENGTH or p.startswith("#")]

        return result

    def split_with_indices(self, text: str) -> list[dict]:
        """
        Split text and return paragraphs with their 1-based indices.

        Returns
        -------
        list[dict]
            Each dict has keys: ``index`` (int), ``text`` (str).
        """
        paragraphs = self.split(text)
        return [
            {"index": i + 1, "text": para}
            for i, para in enumerate(paragraphs)
        ]

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    def _is_noise(self, block: str) -> bool:
        """Check if a block matches known noise patterns or is purely structural."""
        if any(pattern.match(block) for pattern in self.NOISE_PATTERNS):
            return True
            
        block_lower = block.lower()
        
        # Filter out table of contents blocks
        if "table of contents" in block_lower and len(block) < 300:
            return True
            
        # Drop Markdown tables if they are just structural (e.g., Docling outputs |---|---|)
        if block.startswith("|") and block.endswith("|"):
            # Simple check for markdown table separator row
            if re.match(r"^\|[-\s\|]+\|$", block):
                return True

        return False
