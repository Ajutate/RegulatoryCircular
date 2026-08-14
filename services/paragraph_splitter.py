"""
Paragraph Splitter
===================
Splits raw extracted text into meaningful regulatory paragraphs.
Handles edge cases like headers, footers, short lines, and page markers.
"""

import re


class ParagraphSplitter:
    """
    Split raw document text into a list of meaningful paragraphs.

    The splitter:
    1. Splits on double-newlines and common section breaks.
    2. Filters out very short fragments (headers, page numbers).
    3. Merges orphaned short lines with their neighbours.
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

        # Step 2: Split on double newlines (paragraph boundaries)
        raw_blocks = re.split(r"\n{2,}", text)

        # Step 3: Clean each block
        cleaned_blocks = []
        for block in raw_blocks:
            block = self._clean_block(block)
            if block:
                cleaned_blocks.append(block)

        # Step 4: Filter noise (page numbers, headers, footers)
        filtered_blocks = [
            b for b in cleaned_blocks if not self._is_noise(b)
        ]

        # Step 5: PyMuPDF blocks are already grouped. We skip aggressive merging 
        # to preserve headers, TOC items, and short bullet points.
        merged = filtered_blocks

        # Step 6: Final filter — remove anything still too short
        result = [p for p in merged if len(p) >= self.MIN_PARAGRAPH_LENGTH]

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

    @staticmethod
    def _clean_block(block: str) -> str:
        """Collapse internal whitespace and strip a text block."""
        # Replace single newlines with spaces (un-wrap lines)
        cleaned = re.sub(r"\n\s*", " ", block)
        # Collapse multiple spaces
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        return cleaned.strip()

    def _is_noise(self, block: str) -> bool:
        """Check if a block matches known noise patterns."""
        return any(pattern.match(block) for pattern in self.NOISE_PATTERNS)

    def _merge_short_blocks(self, blocks: list[str]) -> list[str]:
        """Merge blocks shorter than MIN_PARAGRAPH_LENGTH with neighbours."""
        if not blocks:
            return []

        merged: list[str] = []
        buffer = ""

        for block in blocks:
            if len(block) < self.MIN_PARAGRAPH_LENGTH:
                # Append short block to buffer
                buffer = f"{buffer} {block}".strip() if buffer else block
            else:
                if buffer:
                    # Prepend buffer to current block
                    block = f"{buffer} {block}"
                    buffer = ""
                merged.append(block)

        # Handle trailing buffer
        if buffer:
            if merged:
                merged[-1] = f"{merged[-1]} {buffer}"
            else:
                merged.append(buffer)

        return merged
