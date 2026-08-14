"""
Regulatory Analyzer
====================
Core LangChain chain that sends regulatory paragraphs to the LLM and
receives structured analysis results.

For Ollama models via LiteLLM:
  - Primary path: with_structured_output() (uses tool-calling if model supports it)
  - Fallback path: raw LLM call + JSON extraction from response text
    (for models that don't support function-calling but respond with valid JSON)
"""

import json
import re
from typing import Callable, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from core.llm import get_llm
from core.prompts import get_system_prompt, get_user_prompt
from core.schemas import RegulatoryParagraphAnalysis
from core.logger import get_logger

logger = get_logger(__name__)


class RegulatoryAnalyzer:
    """
    Analyse regulatory paragraphs using an LLM via LangChain + LiteLLM proxy.

    Supports both cloud models (via tool-calling structured output) and local
    Ollama models (with a JSON-extraction fallback for models that don't fully
    support function-calling).
    """

    def __init__(self) -> None:
        self._llm = get_llm()
        self._system_prompt = get_system_prompt()

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def analyze_paragraph(
        self,
        paragraph: str,
        paragraph_number: int,
        total_paragraphs: int,
    ) -> RegulatoryParagraphAnalysis:
        """
        Analyse a single regulatory paragraph.

        Tries with_structured_output() first; falls back to raw JSON parsing
        if the model doesn't support tool-calling (common with Ollama models).
        """
        user_prompt = get_user_prompt(paragraph, paragraph_number, total_paragraphs)
        logger.info(f"User Prompt:: {user_prompt}")
        logger.info(f"\n\nSystem Prompt:: {self._system_prompt}")
        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=user_prompt),
        ]

        logger.debug(f"Analyzing paragraph {paragraph_number}/{total_paragraphs} using LLM...")
        # ── Primary path: structured output (tool-calling) ──
        try:
            structured_llm = self._llm.with_structured_output(
                RegulatoryParagraphAnalysis
            )
            result = structured_llm.invoke(messages)
            result.paragraph_text = paragraph  # always preserve original
            logger.info(f"Successfully analyzed paragraph {paragraph_number}/{total_paragraphs} (Structured output)")
            logger.info(f"Structured Result: {result.model_dump() if hasattr(result, 'model_dump') else result}")
            return result
        except Exception as e:
            logger.warning(f"Structured output failed for paragraph {paragraph_number}/{total_paragraphs}: {e}. Falling back to raw JSON.")
            pass  # fall through to JSON parsing fallback

        # ── Fallback path: raw LLM call + JSON extraction ──
        logger.debug(f"Using fallback raw JSON extraction for paragraph {paragraph_number}/{total_paragraphs}")
        raw = self._llm.invoke(messages)
        raw_text = raw.content if hasattr(raw, "content") else str(raw)
        result = self._parse_json_response(raw_text, paragraph)
        logger.info(f"Successfully analyzed paragraph {paragraph_number}/{total_paragraphs} (Fallback path)")
        logger.info(f"Fallback Result: {result.model_dump() if hasattr(result, 'model_dump') else result}")
        return result

    def analyze_all(
        self,
        paragraphs: list[str],
        on_progress: Optional[Callable[[int, int, RegulatoryParagraphAnalysis], None]] = None,
    ) -> list[RegulatoryParagraphAnalysis]:
        """
        Analyse all paragraphs sequentially with optional progress callback.
        """
        total = len(paragraphs)
        results: list[RegulatoryParagraphAnalysis] = []
        
        logger.info(f"Starting batch analysis of {total} paragraphs")

        for idx, paragraph in enumerate(paragraphs, start=1):
            try:
                result = self.analyze_paragraph(paragraph, idx, total)
            except Exception as exc:
                logger.error(f"Error analyzing paragraph {idx}: {exc}", exc_info=True)
                result = RegulatoryParagraphAnalysis(
                    paragraph_text=paragraph,
                    para_type="Error",
                    has_effective_date="No",
                    effective_date=None,
                    business_unit="Unknown",
                    theme="Unknown",
                    control_object_name="Unknown",
                    actionable=f"LLM analysis failed: {exc}",
                    level_1="Unknown",
                    level_2="Unknown",
                    level_3="Unknown",
                )

            results.append(result)
            if on_progress:
                on_progress(idx, total, result)

        logger.info(f"Batch analysis complete for {total} paragraphs")
        return results

    # ------------------------------------------------------------------ #
    #  JSON fallback parser (for Ollama models without tool-calling)     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_json_response(
        text: str, original_paragraph: str
    ) -> RegulatoryParagraphAnalysis:
        """
        Extract a JSON object from a raw LLM text response.

        Handles common Ollama output patterns:
          - Pure JSON object
          - JSON wrapped in ```json ... ``` fences
          - JSON preceded by an explanation sentence
        """
        # Strip markdown fences if present
        text = re.sub(r"```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
        text = text.replace("```", "").strip()

        # Try to find the first {...} block
        json_match = re.search(r"\{[\s\S]+\}", text)
        if not json_match:
            raise ValueError(f"No JSON object found in LLM response: {text[:200]}")

        data = json.loads(json_match.group())

        # Always override paragraph_text with the original to prevent hallucination
        data["paragraph_text"] = original_paragraph

        # Normalise has_effective_date to Yes/No
        hed = str(data.get("has_effective_date", "No")).strip().lower()
        data["has_effective_date"] = "Yes" if hed in ("yes", "true", "1") else "No"

        # Ensure effective_date is None when not present
        if data.get("effective_date") in (None, "", "null", "N/A", "n/a"):
            data["effective_date"] = None

        return RegulatoryParagraphAnalysis(**data)
