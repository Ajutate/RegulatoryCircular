"""
Prompt Templates
=================
System and user prompts for the regulatory document analysis chain.

Uses the Agent Skills pattern for progressive disclosure:
- Base system prompt defines the task and output format
- Domain-specific taxonomy (business units, themes, levels) is injected
  dynamically from matched SKILL.md files via core.skill_loader
"""

import json

# ── JSON output template (shown to the model as a concrete example) ──
_JSON_TEMPLATE = json.dumps({
    "paragraph_text": "<exact paragraph text>",
    "para_type": "Action Para | Information Para | Future Effective | Product or Service Not Offered | One-Time Action | Event Based | Repealed | Subsumed",
    "has_effective_date": "Yes | No",
    "effective_date": "DD/MM/YYYY or null",
    "business_unit": "<determined from activated skill context>",
    "theme": "<determined from activated skill context>",
    "control_object_name": "<determined from activated skill context>",
    "actionable": "<concise description of required action, or 'No action required'>",
    "level_1": "<determined from activated skill context>",
    "level_2": "<determined from activated skill context>",
    "level_3": "<determined from activated skill context>",
}, indent=2)

# ── Base system prompt (without hardcoded taxonomy) ──
_BASE_SYSTEM_PROMPT = f"""You are an expert regulatory compliance analyst with deep knowledge of banking regulations, financial services compliance, and regulatory circular interpretation.

Your task is to analyse individual paragraphs from regulatory documents (circulars, guidelines, directives) issued by regulators such as the RBI, SEBI, IRDAI, or similar bodies.

To accurately classify the business unit, theme, control objective, and level taxonomies, you have access to a `read_skill` tool.

AGENT WORKFLOW:
1. Read the paragraph and check the "Available Skills" listed at the end of this prompt.
2. If the paragraph relates to one of the skills, you MUST call the `read_skill` tool with the skill's name to learn the specific classification values.
3. After reading the skill (or if no skill applies), proceed to generate your final analysis.

For each paragraph provided, you must extract and classify the following information:

1. **Paragraph Type (para_type)**: Classify the paragraph as one of:
   - "Action Para" — requires specific action from the institution
   - "Information Para" — provides background or contextual information
   - "Future Effective" — relates to requirements that will become effective at a future date
   - "Product or Service Not Offered" — relates to products or services that the institution does not currently offer
   - "One-Time Action" — requires a single, non-recurring action to be taken
   - "Event Based" — action required based on the occurrence of a specific event
   - "Repealed" — refers to a regulation or clause that has been revoked or repealed
   - "Subsumed" — refers to a regulation that has been subsumed or integrated into another

2. **Is Regulation Para Effective Date Provided (has_effective_date) & Regulation para Effective Date (effective_date)**: Determine if the paragraph mentions an effective date, applicability date, or implementation deadline. If yes, extract the date in DD/MM/YYYY format. Set effective_date to null if none found.

3. **Business Unit (business_unit)**: Identify which business unit within a financial institution is most impacted. Use the classification values provided in the activated skill context.

4. **Theme (theme)**: Identify the overarching regulatory theme. Use the classification values provided in the activated skill context.

5. **Control Objective Name (control_object_name)**: Identify the control objective. Use the classification values provided in the activated skill context.

6. **Actionable (actionable)**: A concise description of the action required. If purely informational, state "No action required".

7. **Level 1 (level_1)**: Top-level taxonomy. Use the classification values provided in the activated skill context.

8. **Level 2 (level_2)**: Second-level taxonomy. Use the classification values provided in the activated skill context.

9. **Level 3 (level_3)**: Third-level (most specific) taxonomy. Use the classification values provided in the activated skill context.

IMPORTANT RULES:
- Be precise and consistent in your classifications.
- If a paragraph spans multiple business units, choose the PRIMARY one.
- Always copy the original paragraph text exactly as provided into "paragraph_text".
- Dates MUST be in DD/MM/YYYY format. If no date exists, set effective_date to null and has_effective_date to "No".
- If a paragraph is too short or lacks meaningful regulatory content (e.g. "Dear Sir/Madam"), classify it as "Information Para" with "No action required".
- If a paragraph is a document title, table of contents, header, footer, or other structural/non-regulatory text, classify it as "Information Para", set actionable to "Not Applicable", and set business_unit and taxonomies to "N/A".

OUTPUT FORMAT — Once you have gathered the necessary context via tools, your FINAL response MUST be ONLY valid JSON matching this exact structure, with no additional text, explanation, or markdown fences:

{_JSON_TEMPLATE}"""

# ── Legacy SYSTEM_PROMPT kept for backward compatibility with get_default_system_prompt() ──
SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT


# ── Default user prompt template (used when no DB override exists) ──
_DEFAULT_USER_PROMPT_TEMPLATE = (
    "Analyse the following regulatory paragraph "
    "(paragraph {paragraph_number} of {total_paragraphs}).\n\n"
    "--- BEGIN PARAGRAPH ---\n"
    "{paragraph}\n"
    "--- END PARAGRAPH ---\n\n"
    "Remember to call the read_skill tool FIRST if a skill applies. Once you have the skill context, respond with ONLY the final JSON object. No markdown fences."
)


def get_system_prompt(discovery_summary: str = "") -> str:
    """Return the system prompt — DB override if admin has set one, else code default."""
    from services.database import get_db_prompt
    db_prompt = get_db_prompt("system")
    
    if db_prompt:
        if "{discovery_summary}" in db_prompt:
            return db_prompt.replace("{discovery_summary}", discovery_summary)
        else:
            return db_prompt + "\n\n" + discovery_summary
    else:
        from core.prompts import _BASE_SYSTEM_PROMPT
        if "{discovery_summary}" in _BASE_SYSTEM_PROMPT:
            return _BASE_SYSTEM_PROMPT.replace("{discovery_summary}", discovery_summary)
        return _BASE_SYSTEM_PROMPT + ("\n\n" + discovery_summary if discovery_summary else "")


def get_default_system_prompt() -> str:
    """Return the hardcoded default system prompt (for Admin UI display)."""
    return SYSTEM_PROMPT


def get_user_prompt(paragraph: str, paragraph_number: int, total_paragraphs: int) -> str:
    """
    Build the user prompt — DB override if admin has set one, else code default.

    Parameters
    ----------
    paragraph : str
        The paragraph text to analyse.
    paragraph_number : int
        The 1-based index of this paragraph within the document.
    total_paragraphs : int
        The total number of paragraphs in the document (for context).
    """
    from services.database import get_db_prompt
    db_template = get_db_prompt("user")
    template = db_template if db_template else _DEFAULT_USER_PROMPT_TEMPLATE
    return template.format(
        paragraph=paragraph,
        paragraph_number=paragraph_number,
        total_paragraphs=total_paragraphs,
    )


def get_default_user_prompt_template() -> str:
    """Return the hardcoded default user prompt template (for Admin UI display)."""
    return _DEFAULT_USER_PROMPT_TEMPLATE


def get_batch_user_prompt(paragraphs: list[str], start_index: int) -> str:
    """
    Build a user prompt for analysing multiple paragraphs in one LLM call.

    Parameters
    ----------
    paragraphs : list[str]
        List of paragraph texts to analyse.
    start_index : int
        The 1-based starting index for numbering.
    """
    formatted_paragraphs = []
    for i, para in enumerate(paragraphs, start=start_index):
        formatted_paragraphs.append(f"### Paragraph {i}\n{para}")

    joined = "\n\n".join(formatted_paragraphs)
    return (
        f"Analyse the following {len(paragraphs)} regulatory paragraphs. "
        f"Return a structured JSON analysis for EACH paragraph.\n\n"
        f"{joined}\n\n"
        f"Respond with ONLY a JSON array of objects. No explanation or markdown."
    )
