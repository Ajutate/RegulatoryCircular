---
name: lending-credit
description: >
  Lending operations, credit policy, loan documentation, NPA management,
  priority sector lending, and loan recovery. Use when the paragraph
  mentions loan, lending, NPA, credit, priority sector, PSL, mortgage,
  collateral, loan recovery, SARFAESI, DRT, loan documentation, or
  credit appraisal.
---

## Classification Values

### Business Unit
**Corporate Banking** (for large/corporate loans)
or **Business Banking - Working Capital** (for working capital facilities)
or **Retail Branch Banking - Retail Agri** (for agri/priority sector)

### Themes
- Process
- Customer Loan Documentation
- Monitoring
- Governance
- Verification

### Levels

| Level 1 | Level 2 | Level 3 |
|---------|---------|---------|
| Risk Management | Credit Risk | Loan Provisioning |
| Risk Management | Credit Risk | NPA Classification |
| Risk Management | Credit Risk | Exposure Limits |
| Compliance | Regulatory Compliance | Priority Sector Targets |
| Operations | Loan Operations | Loan Documentation |
| Operations | Loan Operations | Disbursement Controls |
| Customer Management | Customer Communication | Loan Terms Communication |

### Control Objectives
- Documentation
- Process and Policy
- Risk
- Compliance Monitoring

## Few-Shot Examples

### Example 1
**Paragraph**: "Banks shall classify a loan account as Non-Performing Asset (NPA) if interest and/or instalment of principal remains overdue for a period of more than 90 days."

**Classification**:
- para_type: "Action Para"
- has_effective_date: "No"
- effective_date: null
- business_unit: "Corporate Banking"
- theme: "Process"
- control_object_name: "Process and Policy"
- level_1: "Risk Management"
- level_2: "Credit Risk"
- level_3: "NPA Classification"
- actionable: "Classify loan accounts as NPA when interest/principal overdue exceeds 90 days"

### Example 2
**Paragraph**: "Banks shall achieve a minimum of 40% of Adjusted Net Bank Credit (ANBC) as priority sector lending, of which 18% shall be towards agriculture."

**Classification**:
- para_type: "Action Para"
- has_effective_date: "No"
- effective_date: null
- business_unit: "Retail Branch Banking - Retail Agri"
- theme: "Monitoring"
- control_object_name: "Compliance Monitoring"
- level_1: "Compliance"
- level_2: "Regulatory Compliance"
- level_3: "Priority Sector Targets"
- actionable: "Achieve minimum 40% of ANBC as priority sector lending with 18% to agriculture"
