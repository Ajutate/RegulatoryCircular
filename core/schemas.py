"""
Pydantic Schemas for Structured LLM Output
============================================
These models define the exact structure the LLM must return when analysing
each regulatory paragraph.  Using ``with_structured_output()`` in LangChain
forces the LLM to conform to these schemas, eliminating manual JSON parsing.
"""

from typing import Optional, List, Any

from pydantic import BaseModel, Field, field_validator
from core.skill_loader import ALLOWED_PARA_TYPES, normalize_para_type, APPROVED_THEMES, normalize_theme
from core.date_utils import parse_date_to_dmy


class RegulatoryParagraphAnalysis(BaseModel):
    """Structured analysis of a single regulatory paragraph."""

    paragraph_text: str = Field(
        default="",
        description="The original paragraph text extracted from the regulatory document."
    )

    para_type: str = Field(
        default="Information Para",
        description=(
            "The type of regulatory paragraph. "
            "Must be EXACTLY one of: 'Action Para', 'Information Para', 'Future Effective', "
            "'Product or Service Not Offered', 'One-Time Action', 'Event Based', 'Repealed', 'Subsumed'."
        )
    )

    has_effective_date: str = Field(
        default="No",
        description=(
            "Whether the paragraph specifies an effective / applicability date. "
            "Must be exactly 'Yes' or 'No'."
        )
    )

    effective_date: Optional[str] = Field(
        default=None,
        description=(
            "The effective date mentioned in the paragraph in DD/MM/YYYY format. "
            "Set to null if no date is found."
        ),
    )

    business_unit: str = Field(
        default="N/A",
        description=(
            "The business unit this paragraph is most relevant to. "
            "Must be exactly one value from the Business Unit list in the relevant SKILL.md "
            "(knowledge/skills/*/SKILL.md). Use 'N/A' only for structural or non-regulatory text."
        )
    )

    theme: str = Field(
        default="Process",
        description=(
            "The overarching regulatory theme. MUST be EXACTLY one of the 20 approved themes: "
            "'Assessment', 'Automation', 'Customer Communication', 'Customer Loan Documentation', "
            "'Declaration', 'Definition', 'Disclosure', 'External Communication (other than customer)', "
            "'Governance', 'Information', 'Internal Communication', 'Internal Communication (within bank, staff, branches)', "
            "'Monitoring', 'Notification', 'Policy', 'Process', 'Storage and records keeping', "
            "'System configuration', 'Themes/ Other Attributes', 'Verification'. "
            "Note: 'Exception Handling' and 'Operations' are NOT themes. Use 'N/A' only for structural text."
        )
    )

    control_object_name: str = Field(
        default="N/A",
        description=(
            "The control objective addressed by this paragraph. "
            "Examples: 'Risk', 'Communication', 'Process and Policy', "
            "'Documentation', 'Audit Trail', 'Segregation of Duties', "
            "'Access Control', 'Compliance Monitoring'. "
            "Use 'N/A' if structural or non-regulatory text."
        )
    )

    actionable: str = Field(
        default="No action required",
        description=(
            "A concise description of the action required by this paragraph. "
            "If the paragraph is purely informational, state 'No action required'."
        )
    )

    level_1: str = Field(
        default="N/A",
        description=(
            "Top-level taxonomy classification. "
            "Examples: 'Governance', 'Due Diligence', 'Risk Management', "
            "'Compliance', 'Operations', 'Reporting', 'Customer Management'. "
            "Use 'N/A' if structural or non-regulatory text."
        )
    )

    level_2: str = Field(
        default="N/A",
        description=(
            "Second-level taxonomy classification. "
            "Examples: 'Corporate Governance', 'Access Control', "
            "'Regulatory Reporting', 'Internal Audit', 'Fraud Prevention', "
            "'Credit Risk', 'Operational Risk'. "
            "Use 'N/A' if structural or non-regulatory text."
        )
    )

    level_3: str = Field(
        default="N/A",
        description=(
            "Third-level (most granular) taxonomy classification. "
            "Examples: 'Fit and Proper Criteria', 'Customer Communication', "
            "'Board Composition', 'Loan Provisioning', 'KYC Requirements', "
            "'Transaction Monitoring', 'Capital Buffer'. "
            "Use 'N/A' if structural or non-regulatory text."
        )
    )

    @field_validator("para_type", mode="before")
    @classmethod
    def validate_and_normalize_para_type(cls, v: Any) -> str:
        return normalize_para_type(v)

    @field_validator("theme", mode="before")
    @classmethod
    def validate_and_normalize_theme(cls, v: Any) -> str:
        return normalize_theme(v)

    @field_validator("effective_date", mode="before")
    @classmethod
    def validate_and_normalize_effective_date(cls, v: Any) -> Optional[str]:
        return parse_date_to_dmy(v)


class DocumentAnalysisResult(BaseModel):
    """Complete analysis result for an entire regulatory document."""

    document_name: str = Field(description="Name of the uploaded document.")
    total_paragraphs: int = Field(description="Total number of paragraphs analysed.")
    analyses: List[RegulatoryParagraphAnalysis] = Field(
        default_factory=list,
        description="List of paragraph-level analysis results.",
    )
