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
        from langchain.agents import create_agent
        from core.prompts import get_user_prompt, get_system_prompt
        from core.middleware import SkillMiddleware

        system_prompt = get_system_prompt("")
        user_prompt = get_user_prompt(paragraph, paragraph_number, total_paragraphs)
        
        logger.info(f"User Prompt:: {user_prompt}")
        logger.info(f"\n\nSystem Prompt:: {system_prompt}")
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        logger.debug(f"Analyzing paragraph {paragraph_number}/{total_paragraphs} using Agent Loop...")
        
        from langchain_core.callbacks import BaseCallbackHandler
        class LLMPromptLogger(BaseCallbackHandler):
            def on_chat_model_start(self, serialized, messages, **kwargs):
                # This will print the full list of messages sent to the LLM
                # including the SystemPrompt, UserPrompt, and Tool responses!
                formatted_prompt = "\\n\\n=== FULL PROMPT SENT TO LLM ===\\n"
                for msg_list in messages:
                    for m in msg_list:
                        formatted_prompt += f"\\n--- [Role: {m.type.upper()}] ---\\n"
                        if getattr(m, 'tool_calls', []):
                            formatted_prompt += f"TOOL CALLS: {m.tool_calls}\\n"
                        if getattr(m, 'tool_call_id', None):
                            formatted_prompt += f"TOOL CALL ID: {m.tool_call_id}\\n"
                        formatted_prompt += f"{str(m.content)}\\n"
                formatted_prompt += "=================================\\n\\n"
                logger.info(f"formatted_prompt :: {formatted_prompt}")

        agent = create_agent(model=self._llm, middleware=[SkillMiddleware()])
        
        try:
            result_state = agent.invoke(
                {"messages": messages}, 
                config={"callbacks": [LLMPromptLogger()]}
            )
            
            final_content = result_state["messages"][-1].content
            logger.info(f"Successfully analyzed paragraph {paragraph_number}/{total_paragraphs}")
            return self._parse_json_response(final_content, paragraph)
        except Exception as e:
            logger.error(f"Agent analysis failed for paragraph {paragraph_number}/{total_paragraphs}: {e}")

            # Create a fallback analysis if everything fails
            return RegulatoryParagraphAnalysis(
                paragraph_text=paragraph,
                para_type="Error",
                has_effective_date="No",
                effective_date=None,
                business_unit="Unknown",
                theme="Unknown",
                control_object_name="Unknown",
                actionable=f"Agent or parsing failed: {e}",
                level_1="Unknown",
                level_2="Unknown",
                level_3="Unknown",
            )

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
