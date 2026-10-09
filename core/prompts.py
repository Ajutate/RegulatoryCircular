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
    "business_unit": "<exactly one value from the Business Unit list in the activated skill context>",
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

To accurately classify the business unit, theme, control objective, and level taxonomies, you MUST use the skills (SKILL.md taxonomies). The most relevant skill(s) may already be provided below under "Activated Skill Context". You also have a `read_skill` tool to load any other skill.

AGENT WORKFLOW:
1. Read the paragraph and the "Available Skills" list.
2. You have exactly one tool: `read_skill`. Call `read_skill` with the name of the closest domain skill to load its taxonomy. Do NOT invent or call any other tool.
3. Choose business_unit, theme, control_object_name, level_1, level_2 and level_3 ONLY from the values returned by `read_skill`. Pick the closest match; do NOT invent values and do NOT leave them as N/A.
4. Output your final classification as the JSON object specified below.

For each paragraph provided, you must extract and classify the following information:

1. **Paragraph Type (para_type)**: Classify the paragraph as EXACTLY one of the following 8 predefined types (use the exact spelling verbatim; NEVER return "Information" alone, always use "Information Para"):
   - "Action Para" — requires specific action from the institution
   - "Information Para" — provides background or contextual information
   - "Future Effective" — relates to requirements that will become effective at a future date
   - "Product or Service Not Offered" — relates to products or services that the institution does not currently offer
   - "One-Time Action" — requires a single, non-recurring action to be taken
   - "Event Based" — action required based on the occurrence of a specific event
   - "Repealed" — refers to a regulation or clause that has been revoked or repealed
   - "Subsumed" — refers to a regulation that has been subsumed or integrated into another

2. **Is Regulation Para Effective Date Provided (has_effective_date) & Regulation para Effective Date (effective_date)**: Determine if the paragraph mentions an effective date, applicability date, implementation deadline, release date, or go-live date (e.g. "July 31, 2026", "with effect from October 01, 2025", "before July 31, 2026", "scheduled to be released on live on End of Day of July 31, 2026").
   If ANY such date or deadline is mentioned:
   - Set has_effective_date to "Yes"
   - Extract and convert the date strictly to DD/MM/YYYY format (e.g. "July 31, 2026" becomes "31/07/2026").
   If no date is found, set effective_date to null and has_effective_date to "No".

3. **Business Unit (business_unit)**: Identify which business unit within the bank is most impacted. You MUST choose EXACTLY one value from the "Business Unit" list of the activated skill context (copy it verbatim; the first entries are the most common for that domain). If the paragraph clearly belongs to a different domain, call `read_skill` for that domain and use its Business Unit list. Never invent or modify a business unit name.

4. **Theme (theme)**: Identify the overarching regulatory theme. You MUST choose EXACTLY one value from the 20 approved Themes:
   Assessment, Automation, Customer Communication, Customer Loan Documentation, Declaration, Definition, Disclosure, External Communication (other than customer), Governance, Information, Internal Communication, Internal Communication (within bank, staff, branches), Monitoring, Notification, Policy, Process, Storage and records keeping, System configuration, Themes/ Other Attributes, Verification.
   CRITICAL: "Exception Handling", "Operations", "Compliance", "Risk Management" are NOT themes. NEVER output them as a theme. Choose from the 20 approved themes above only.

5. **Control Objective Name (control_object_name)**: Identify the control objective. Use the classification values provided in the activated skill context.

6. **Actionable (actionable)**: A concise description of the action required. If purely informational, state "No action required".

7. **Level 1 (level_1)**: Top-level taxonomy. Use the classification values provided in the activated skill context.

8. **Level 2 (level_2)**: Second-level taxonomy. Use the classification values provided in the activated skill context.

9. **Level 3 (level_3)**: Third-level (most specific) taxonomy. Use the classification values provided in the activated skill context.

IMPORTANT RULES:
- Be precise and consistent in your classifications.
- para_type MUST strictly be one of: "Action Para", "Information Para", "Future Effective", "Product or Service Not Offered", "One-Time Action", "Event Based", "Repealed", "Subsumed". NEVER truncate "Information Para" to "Information" or "Action Para" to "Action".
- EFFECTIVE DATES: Any mention of effective date, applicability date, implementation deadline, release date, or go-live date (e.g. "scheduled to be released on live on End of Day of July 31, 2026" or "before July 31, 2026") MUST be captured: set has_effective_date to "Yes" and effective_date to DD/MM/YYYY format ("31/07/2026"). Never leave effective_date as null when a date or deadline is stated in the text.
- THEMES: theme MUST strictly be one of the 20 approved themes listed above. "Exception Handling" and "Operations" are NOT themes and must NEVER be used as a theme.
- If a paragraph spans multiple business units, choose the PRIMARY one.
- Always copy the original paragraph text exactly as provided into "paragraph_text".
- Dates MUST be in DD/MM/YYYY format. If no date exists, set effective_date to null and has_effective_date to "No".
- If a paragraph is too short or lacks meaningful regulatory content (e.g. "Dear Sir/Madam"), classify it as "Information Para" with "No action required".
- "N/A" for business_unit, theme, control_object_name and level_1/2/3 is allowed ONLY when the text is purely structural: a document title, table of contents, header, footer, salutation or signature. In that case classify it as "Information Para" and set actionable to "Not Applicable".
- For ANY paragraph with regulatory content (including Information Para, definitions, background), you MUST fill business_unit, theme, control_object_name, level_1, level_2 and level_3 with the closest values from the skill(s). Never return N/A for these.

OUTPUT FORMAT — Once you have the skill context, your FINAL response MUST be ONLY valid JSON matching this exact structure, with no additional text, explanation, or markdown fences:

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
    "CLASSIFICATION RULES:\n"
    "1. para_type MUST be EXACTLY one of: 'Action Para', 'Information Para', 'Future Effective', 'Product or Service Not Offered', 'One-Time Action', 'Event Based', 'Repealed', 'Subsumed'. Use 'Information Para' (never just 'Information').\n"
    "2. theme MUST be EXACTLY one of the 20 approved Themes: Assessment, Automation, Customer Communication, Customer Loan Documentation, Declaration, Definition, Disclosure, External Communication (other than customer), Governance, Information, Internal Communication, Internal Communication (within bank, staff, branches), Monitoring, Notification, Policy, Process, Storage and records keeping, System configuration, Themes/ Other Attributes, Verification. (Do NOT output 'Exception Handling' or 'Operations' as theme).\n"
    "3. effective_date: If the text mentions an effective date, release date, go-live date, or deadline (e.g. 'July 31, 2026'), you MUST set has_effective_date to 'Yes' and effective_date to DD/MM/YYYY (e.g. '31/07/2026').\n"
    "4. Use the skill taxonomy values from the activated skill context for business_unit, control_object_name and level_1/2/3.\n\n"
    "Respond with ONLY the final JSON object. No markdown fences."
)


def get_system_prompt(discovery_summary: str = "") -> str:
    """
    Return the system prompt - DB override if admin has set one, else code default.

    ``discovery_summary`` carries the activated skill context (taxonomy and the
    skill's Business Unit list) and is appended if provided.
    Note: The Available Skills catalog is injected dynamically by SkillMiddleware.
    """
    from services.database import get_db_prompt
    db_prompt = get_db_prompt("system")
    base = db_prompt if db_prompt else _BASE_SYSTEM_PROMPT

    if "{discovery_summary}" in base:
        return base.replace("{discovery_summary}", discovery_summary)
    return base + ("\n\n" + discovery_summary if discovery_summary else "")



def get_default_system_prompt() -> str:
    """Return the hardcoded default system prompt (for Admin UI display)."""
    return SYSTEM_PROMPT


def get_user_prompt(paragraph: str, paragraph_number: int, total_paragraphs: int) -> str:
    """
    Build the user prompt - DB override if admin has set one, else code default.

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
