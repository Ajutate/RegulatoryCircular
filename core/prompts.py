"""
Prompt Templates
=================
System and user prompts for the regulatory document analysis chain.

Ollama note: Local models vary widely in JSON schema adherence.
The system prompt includes an explicit JSON output template to help
smaller models (7B–13B) produce valid structured output even when
tool-calling / function-calling is not fully supported.
LangChain's with_structured_output() uses this as a fallback.
"""

import json

# ── JSON output template (shown to the model as a concrete example) ──
_JSON_TEMPLATE = json.dumps({
    "paragraph_text": "<exact paragraph text>",
    "para_type": "Action Para | Information Para | Future Effective | Product or Service Not Offered | One-Time Action | Event Based | Repealed | Subsumed",
    "has_effective_date": "Yes | No",
    "effective_date": "DD/MM/YYYY or null",
    "business_unit": "Administration | Audit | Business Banking - Working Capital | Compliance - RRD | Finance - ALM | Finance - PAD | Finance - FAG | Human Resources | Information Technology | Legal | Operations | Risk Management | Treasury | Retail Banking | Corporate Banking | Customer Service | N/A",
    "theme": "Monitoring | Process | Reporting | Governance | Risk Management | Customer Protection | Capital Adequacy | Anti-Money Laundering | Data Privacy | Licensing | N/A",
    "control_object_name": "Risk | Communication | Process and Policy | Documentation | Audit Trail | Segregation of Duties | Access Control | Compliance Monitoring | N/A",
    "actionable": "<concise description of required action, or 'No action required'>",
    "level_1": "Governance | Due Diligence | Risk Management | Compliance | Operations | Reporting | Customer Management | N/A",
    "level_2": "Corporate Governance | Access Control | Regulatory Reporting | Internal Audit | Fraud Prevention | Credit Risk | Operational Risk | N/A",
    "level_3": "Fit and Proper Criteria | Customer Communication | Board Composition | Loan Provisioning | KYC Requirements | Transaction Monitoring | Capital Buffer | N/A",
}, indent=2)

SYSTEM_PROMPT = f"""You are an expert regulatory compliance analyst with deep knowledge of banking regulations, financial services compliance, and regulatory circular interpretation.

Your task is to analyse individual paragraphs from regulatory documents (circulars, guidelines, directives) issued by regulators such as the RBI, SEBI, IRDAI, or similar bodies.

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

3. **Business Unit (business_unit)**: Identify which business unit within a financial institution is most impacted. Choose the closest match from:
   Administration, Audit, Business Banking - Working Capital, Compliance - RRD,
   Finance - ALM, Finance - PAD, Finance - FAG, Human Resources,
   Information Technology, Corporate Legal, Operations, Risk Management,
   Treasury, Retail Branch Banking- Retail Forex, Retail Agri, Corporate Banking

4. **Theme (theme)**: Identify the overarching regulatory theme.
   Examples: Assessment, Automation, Customer Communication, Customer Loan Documentation, Declaration, Definition, Disclosure, External Communication(other than customer), Governance, Information, Internal Communication, Internal Communication(within bank, staff, branches), Monitoring, Notification, Policy, Process, Storage and record keeping, System configuration, Themes/ Other Attibutes, Verification

5. **Control Objective Name (control_object_name)**: Identify the control objective.
   Examples: Risk, Communication, Process and Policy, Documentation, Audit Trail, Segregation of Duties, Access Control, Compliance Monitoring

6. **Actionable (actionable)**: A concise description of the action required. If purely informational, state "No action required".

7. **Level 1 (level_1)**: Top-level taxonomy.
   Examples: Communication and Conduct, Governance, Information Technology and Cyber Security,  Due Diligence, Information Technology and Cyber Security, Physical Non IT assests and Safety Controls(admin), Reconciliation(other than Physical Asset), Reporting and Disclosure, Third Party Controls, Training and Employee Code of Conduct, Transaction Controls and Monitoring 


8. **Level 2 (level_2)**: Second-level taxonomy.
   Examples: Corporate Governance, Access Control, Regulatory Reporting, Internal Audit, Fraud Prevention, Credit Risk, Operational Risk

9. **Level 3 (level_3)**: Third-level (most specific) taxonomy.
   Examples: Fit and Proper Criteria, Customer Communication, Board Composition, Loan Provisioning, KYC Requirements, Transaction Monitoring, Capital Buffer

IMPORTANT RULES:
- Be precise and consistent in your classifications.
- If a paragraph spans multiple business units, choose the PRIMARY one.
- Always copy the original paragraph text exactly as provided into "paragraph_text".
- Dates MUST be in DD/MM/YYYY format. If no date exists, set effective_date to null and has_effective_date to "No".
- If a paragraph is too short or lacks meaningful regulatory content (e.g. "Dear Sir/Madam"), classify it as "Information Para" with "No action required".
- If a paragraph is a document title, table of contents, header, footer, or other structural/non-regulatory text, classify it as "Information Para", set actionable to "Not Applicable", and set business_unit and taxonomies to "N/A".

OUTPUT FORMAT — You MUST respond with ONLY valid JSON matching this exact structure, with no additional text, explanation, or markdown fences:

{_JSON_TEMPLATE}"""


# ── Default user prompt template (used when no DB override exists) ──
_DEFAULT_USER_PROMPT_TEMPLATE = (
    "Analyse the following regulatory paragraph "
    "(paragraph {paragraph_number} of {total_paragraphs}).\n\n"
    "--- BEGIN PARAGRAPH ---\n"
    "{paragraph}\n"
    "--- END PARAGRAPH ---\n\n"
    "Respond with ONLY the JSON object. No explanation, no markdown, no extra text."
)


def get_system_prompt() -> str:
    """Return the system prompt — DB override if admin has set one, else code default."""
    from services.database import get_db_prompt
    db_prompt = get_db_prompt("system")
    return db_prompt if db_prompt else SYSTEM_PROMPT


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
