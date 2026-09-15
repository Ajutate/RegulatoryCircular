---
name: compliance-reporting
description: >
  Regulatory reporting, compliance filings, statutory returns, RBI submissions,
  and disclosure requirements. Use when the paragraph mentions regulatory return,
  filing, submission, disclosure, statutory report, annual report, pillar 3,
  Basel disclosure, or compliance report.
---

## Classification Values

### Business Unit
**Compliance - RRD** (for regulatory returns)
or **Finance - PAD** (for financial disclosures)

### Themes
- Reporting
- Disclosure
- Process
- Monitoring

### Levels

| Level 1 | Level 2 | Level 3 |
|---------|---------|---------|
| Reporting and Disclosure | Regulatory Reporting | Statutory Returns |
| Reporting and Disclosure | Regulatory Reporting | Basel Disclosures |
| Reporting and Disclosure | Internal Reporting | MIS Reports |
| Compliance | Regulatory Compliance | Filing Deadlines |

### Control Objectives
- Documentation
- Process and Policy
- Audit Trail
- Compliance Monitoring

## Few-Shot Examples

### Example 1
**Paragraph**: "Banks shall submit the DSB Return (Form A) to RBI on a fortnightly basis within 7 days from the close of the reporting fortnight."

**Classification**:
- para_type: "Action Para"
- has_effective_date: "No"
- effective_date: null
- business_unit: "Compliance - RRD"
- theme: "Reporting"
- control_object_name: "Process and Policy"
- level_1: "Reporting and Disclosure"
- level_2: "Regulatory Reporting"
- level_3: "Statutory Returns"
- actionable: "Submit DSB Return (Form A) to RBI fortnightly within 7 days of reporting fortnight close"

### Example 2
**Paragraph**: "Banks shall make Pillar 3 disclosures under Basel III framework on a quarterly basis on their website."

**Classification**:
- para_type: "Action Para"
- has_effective_date: "No"
- effective_date: null
- business_unit: "Finance - PAD"
- theme: "Disclosure"
- control_object_name: "Documentation"
- level_1: "Reporting and Disclosure"
- level_2: "Regulatory Reporting"
- level_3: "Basel Disclosures"
- actionable: "Publish Pillar 3 Basel III disclosures quarterly on bank website"
