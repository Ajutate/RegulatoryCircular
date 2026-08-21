"""
Paragraph Splitter
===================
Splits raw extracted text into meaningful regulatory paragraphs.

Strategy:
  - Each visual line from the PDF extractor is already on its own line.
  - Lines that start with a bullet marker (•, -, *, ▪, ►, ●, numbered lists)
    are always treated as a new paragraph.
  - Lines separated by blank lines (double newlines) are separate paragraphs.
  - Consecutive "plain" lines (no bullet, no blank line between them) are
    merged together as they are likely continuation of the same paragraph.
  - Noise (page numbers, standalone "Confidential", etc.) is filtered out.
"""

import re


class ParagraphSplitter:
    """
    Split raw document text into a list of meaningful paragraphs.

    Each bullet point and each block separated by blank lines becomes
    its own paragraph.
    """

    # Minimum character length to consider a block a valid paragraph
    MIN_PARAGRAPH_LENGTH = 15

    # Pattern to detect lines that start a new paragraph (bullet points, numbered items)
    BULLET_PATTERN = re.compile(
        r"^\s*("
        r"[\u2022\u2023\u25E6\u2043\u2219\u25AA\u25AB\u25B8\u25B6\u25BA\u25CF\u25CB\u2013\u2014]"  # Unicode bullets/dashes
        r"|[-*•▪►●◦‣⁃]"          # Common ASCII/symbol bullets
        r"|\d+[.)]\s"              # Numbered list: 1. or 1) followed by space
        r"|[a-zA-Z][.)]\s"        # Lettered list: a. or a) followed by space
        r"|\([a-zA-Z0-9]+\)\s"   # Parenthesized list: (a) or (1) followed by space
        r"|[ivxlIVXL]+[.)]\s"    # Roman numeral list: i. or iv) followed by space
        r")"
    )

    # Patterns for content that should be filtered out
    NOISE_PATTERNS = [
        re.compile(r"^\s*page\s*\d+\s*(of\s*\d+)?\s*$", re.IGNORECASE),
        re.compile(r"^\s*-\s*\d+\s*-\s*$"),
        re.compile(r"^\s*\d+\s*$"),
        re.compile(r"^\s*confidential\s*$", re.IGNORECASE),
        re.compile(r"^\s*draft\s*$", re.IGNORECASE),
    ]

    def split(self, text: str) -> list[str]:
        """
        Split raw text into a list of cleaned paragraphs.

        Parameters
        ----------
        text : str
            The full extracted text of the document.

        Returns
        -------
        list[str]
            List of paragraph strings, each containing meaningful content.
        """
        if not text or not text.strip():
            return []

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

            # Bullet/numbered line → flush previous paragraph, start new one
            if self.BULLET_PATTERN.match(stripped):
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

        # Step 4: Filter noise (page numbers, headers, footers)
        filtered = [p for p in paragraphs if not self._is_noise(p)]

        # Step 5: Final filter — remove anything still too short
        result = [p for p in filtered if len(p) >= self.MIN_PARAGRAPH_LENGTH]

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
        """Check if a block matches known noise patterns."""
        return any(pattern.match(block) for pattern in self.NOISE_PATTERNS)
