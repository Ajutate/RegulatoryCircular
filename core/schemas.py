"""
Pydantic Schemas for Structured LLM Output
============================================
These models define the exact structure the LLM must return when analysing
each regulatory paragraph.  Using ``with_structured_output()`` in LangChain
forces the LLM to conform to these schemas, eliminating manual JSON parsing.
"""

from typing import Optional, List

from pydantic import BaseModel, Field


class RegulatoryParagraphAnalysis(BaseModel):
    """Structured analysis of a single regulatory paragraph."""

    paragraph_text: str = Field(
        description="The original paragraph text extracted from the regulatory document."
    )

    para_type: str = Field(
        description=(
            "The type of regulatory paragraph. "
            "Examples: 'Action Para', 'Information Para', 'Future Effective', "
            "'Product or Service Not Offered', 'One-Time Action', 'Event Based', 'Repealed', 'Subsumed'."
        )
    )

    has_effective_date: str = Field(
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
        description=(
            "The business unit this paragraph is most relevant to. "
            "Choose from: Administration, Audit, Business Banking - Working Capital, "
            "Compliance - RRD, Finance - ALM, Finance - PAD, Finance - FAG, "
            "Human Resources, Information Technology, Legal, Operations, "
            "Risk Management, Treasury, Retail Banking, Corporate Banking, "
            "Customer Service. "
            "If none fit precisely, suggest the closest match. Use 'N/A' if structural or non-regulatory text."
        )
    )

    theme: str = Field(
        description=(
            "The overarching theme of the paragraph. "
            "Examples: 'Monitoring', 'Process', 'Reporting', 'Governance', "
            "'Risk Management', 'Customer Protection', 'Capital Adequacy', "
            "'Anti-Money Laundering', 'Data Privacy', 'Licensing'. "
            "Use 'N/A' if structural or non-regulatory text."
        )
    )

    control_object_name: str = Field(
        description=(
            "The control objective addressed by this paragraph. "
            "Examples: 'Risk', 'Communication', 'Process and Policy', "
            "'Documentation', 'Audit Trail', 'Segregation of Duties', "
            "'Access Control', 'Compliance Monitoring'. "
            "Use 'N/A' if structural or non-regulatory text."
        )
    )

    actionable: str = Field(
        description=(
            "A concise description of the action required by this paragraph. "
            "If the paragraph is purely informational, state 'No action required'."
        )
    )

    level_1: str = Field(
        description=(
            "Top-level taxonomy classification. "
            "Examples: 'Governance', 'Due Diligence', 'Risk Management', "
            "'Compliance', 'Operations', 'Reporting', 'Customer Management'. "
            "Use 'N/A' if structural or non-regulatory text."
        )
    )

    level_2: str = Field(
        description=(
            "Second-level taxonomy classification. "
            "Examples: 'Corporate Governance', 'Access Control', "
            "'Regulatory Reporting', 'Internal Audit', 'Fraud Prevention', "
            "'Credit Risk', 'Operational Risk'. "
            "Use 'N/A' if structural or non-regulatory text."
        )
    )

    level_3: str = Field(
        description=(
            "Third-level (most granular) taxonomy classification. "
            "Examples: 'Fit and Proper Criteria', 'Customer Communication', "
            "'Board Composition', 'Loan Provisioning', 'KYC Requirements', "
            "'Transaction Monitoring', 'Capital Buffer'. "
            "Use 'N/A' if structural or non-regulatory text."
        )
    )


class DocumentAnalysisResult(BaseModel):
    """Complete analysis result for an entire regulatory document."""

    document_name: str = Field(description="Name of the uploaded document.")
    total_paragraphs: int = Field(description="Total number of paragraphs analysed.")
    analyses: List[RegulatoryParagraphAnalysis] = Field(
        default_factory=list,
        description="List of paragraph-level analysis results.",
    )
