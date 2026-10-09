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

        logger.debug(f"Analyzing paragraph {paragraph_number}/{total_paragraphs} using Agent Loop with SkillMiddleware...")
        
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

    # ------------------------------------------------------------------ #
    #  Skill selection                                                    #
    # ------------------------------------------------------------------ #

    def _resolve_skills(self, paragraph: str) -> list[str]:
        """Pick skills by keyword match; if none match, ask the LLM to route."""
        from core.skill_loader import select_skills, load_skill_index

        names = select_skills(paragraph)
        if names:
            return names

        index = load_skill_index()
        valid = [s["name"] for s in index]
        catalog = "\n".join(f"- {s['name']}: {s['description']}" for s in index)
        try:
            resp = self._llm.invoke([
                SystemMessage(content=(
                    "You route regulatory paragraphs to the most relevant classification skill. "
                    "Reply with ONLY the exact skill name from the list (you may give up to 2, comma-separated). "
                    "You must always pick the closest skill.\n\n" + catalog
                )),
                HumanMessage(content=paragraph),
            ])
            text = str(resp.content).lower()
            return [n for n in valid if n in text][:2]
        except Exception as e:
            logger.warning(f"Skill routing failed: {e}")
            return []

    @staticmethod
    def _build_skill_context(skill_names: list[str]) -> str:
        from core.skill_loader import load_skill_body

        sections = []
        for name in skill_names:
            body = load_skill_body(name)
            if body:
                sections.append(f"### Skill: {name}\n\n{body}")
        if not sections:
            return ""
        return "## Activated Skill Context\n\n" + "\n\n".join(sections)

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

        # Harmonize effective date across all paragraphs if any date is present
        from core.date_utils import harmonize_document_effective_dates
        harmonize_document_effective_dates(results)

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

        # Debug logging to see exactly what JSON the LLM returned
        logger.error(f"RAW JSON EXTRACTED FROM LLM: {json.dumps(data, indent=2)}")
        
        # If the LLM returned {"Examples": [...]} or [{"para_type": ...}], extract from it
        if ("para_type" not in data) and any(k.lower() in ("examples", "results", "items") for k in data):
            for k in list(data.keys()):
                if k.lower() in ("examples", "results", "items") and isinstance(data[k], list) and len(data[k]) > 0:
                    first_item = data[k][0]
                    if isinstance(first_item, dict):
                        if any(ck.lower() == "classification" for ck in first_item):
                            c_val = next(v for ck, v in first_item.items() if ck.lower() == "classification")
                            if isinstance(c_val, dict):
                                data = c_val
                        else:
                            data = first_item
                    break

        # If the LLM nested the output inside a "classification", "analysis", or "result" object, lift it
        for k in list(data.keys()):
            if k.lower() in ("classification", "analysis", "result", "output") and isinstance(data[k], dict):
                for sub_k, sub_v in data[k].items():
                    data[sub_k] = sub_v

        # Map alternate key names
        if "paragraph" in data and not data.get("paragraph_text"):
            data["paragraph_text"] = data["paragraph"]
        if "paragraph_type" in data and not data.get("para_type"):
            data["para_type"] = data["paragraph_type"]
        elif "type" in data and not data.get("para_type"):
            data["para_type"] = data["type"]
        if "control_objective" in data and not data.get("control_object_name"):
            data["control_object_name"] = data["control_objective"]
        elif "control_objective_name" in data and not data.get("control_object_name"):
            data["control_object_name"] = data["control_objective_name"]
        if "action" in data and not data.get("actionable"):
            data["actionable"] = data["action"]
        elif "action_required" in data and not data.get("actionable"):
            data["actionable"] = data["action_required"]

        # Always override paragraph_text with the original to prevent hallucination
        data["paragraph_text"] = original_paragraph

        # Normalise and extract effective date
        from core.date_utils import parse_date_to_dmy, extract_effective_date_from_text

        parsed_llm_date = parse_date_to_dmy(data.get("effective_date"))
        if not parsed_llm_date:
            has_d, text_date = extract_effective_date_from_text(original_paragraph)
            if has_d == "Yes" and text_date:
                logger.info(f"Captured effective date '{text_date}' from paragraph text")
                data["has_effective_date"] = "Yes"
                data["effective_date"] = text_date
            else:
                data["has_effective_date"] = "No"
                data["effective_date"] = None
        else:
            data["has_effective_date"] = "Yes"
            data["effective_date"] = parsed_llm_date

        # Snap business_unit, theme, and para_type to their approved lists (exact spelling)
        from core.skill_loader import (
            normalize_business_unit,
            normalize_theme,
            normalize_levels,
            normalize_para_type,
        )
        data["para_type"] = normalize_para_type(data.get("para_type"))
        data["business_unit"] = normalize_business_unit(data.get("business_unit"))
        data["theme"] = normalize_theme(data.get("theme"))
        
        # Provide defaults for commonly omitted fields
        if not data.get("control_object_name"):
            data["control_object_name"] = "N/A"
        if not data.get("actionable"):
            data["actionable"] = "No action required" if data["para_type"] == "Information Para" else "N/A"
            
        # Snap levels to the approved global hierarchy
        l1, l2, l3 = normalize_levels(
            data.get("level_1"), 
            data.get("level_2"), 
            data.get("level_3")
        )
        data["level_1"] = l1
        data["level_2"] = l2
        data["level_3"] = l3

        return RegulatoryParagraphAnalysis(**data)
