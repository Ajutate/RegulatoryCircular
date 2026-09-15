---
name: aml-kyc
description: >
  Anti-money laundering, know your customer, customer due diligence,
  suspicious transaction reporting, PML Act compliance, and CFT measures.
  Use when the paragraph mentions KYC, AML, PMLA, suspicious transaction,
  STR, CTR, customer identification, due diligence, PEP, beneficial owner,
  money laundering, or terrorist financing.
---

## Classification Values

### Business Unit
**Compliance - RRD**

### Themes
- Verification
- Monitoring
- Process
- Reporting
- Customer Communication

### Levels

| Level 1 | Level 2 | Level 3 |
|---------|---------|---------|
| Due Diligence | Customer Due Diligence | KYC Requirements |
| Due Diligence | Customer Due Diligence | Enhanced Due Diligence |
| Due Diligence | Customer Due Diligence | Beneficial Ownership |
| Transaction Controls and Monitoring | AML Monitoring | Transaction Monitoring |
| Transaction Controls and Monitoring | AML Monitoring | Suspicious Transaction Reporting |
| Reporting and Disclosure | Regulatory Reporting | CTR Filing |
| Compliance | Regulatory Compliance | PMLA Compliance |

### Control Objectives
- Compliance Monitoring
- Documentation
- Process and Policy
- Risk

## Few-Shot Examples

### Example 1
**Paragraph**: "Banks shall carry out Customer Due Diligence (CDD) at the time of opening a new account, including verification of identity using officially valid documents as defined under the PMLA Rules."

**Classification**:
- para_type: "Action Para"
- has_effective_date: "No"
- effective_date: null
- business_unit: "Compliance - RRD"
- theme: "Verification"
- control_object_name: "Process and Policy"
- level_1: "Due Diligence"
- level_2: "Customer Due Diligence"
- level_3: "KYC Requirements"
- actionable: "Perform CDD at account opening using officially valid documents per PMLA Rules"

### Example 2
**Paragraph**: "Cash Transaction Reports (CTRs) for all cash transactions of Rs. 10 lakh and above shall be filed with FIU-IND within 15 days of the close of the month."

**Classification**:
- para_type: "Action Para"
- has_effective_date: "No"
- effective_date: null
- business_unit: "Compliance - RRD"
- theme: "Reporting"
- control_object_name: "Compliance Monitoring"
- level_1: "Reporting and Disclosure"
- level_2: "Regulatory Reporting"
- level_3: "CTR Filing"
- actionable: "File CTRs for cash transactions of Rs 10 lakh and above with FIU-IND within 15 days of month-end"
