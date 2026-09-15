---
name: treasury-operations
description: >
  Treasury management, investment portfolio, SLR/CRR maintenance,
  ALM (Asset Liability Management), interest rate management, and
  capital adequacy. Use when the paragraph mentions treasury, SLR,
  CRR, investment, capital adequacy, CRAR, Basel, capital buffer,
  ALM, interest rate, liquidity, or reserve requirements.
---

## Classification Values

### Business Unit
**Treasury** (for investment/trading)
or **Finance - ALM** (for asset-liability management)

### Themes
- Process
- Monitoring
- Governance
- Reporting

### Levels

| Level 1 | Level 2 | Level 3 |
|---------|---------|---------|
| Risk Management | Market Risk | Interest Rate Risk |
| Risk Management | Liquidity Risk | Liquidity Coverage Ratio |
| Compliance | Regulatory Compliance | Reserve Requirements |
| Compliance | Regulatory Compliance | Capital Adequacy |
| Transaction Controls and Monitoring | Investment Controls | Portfolio Limits |

### Control Objectives
- Risk
- Process and Policy
- Compliance Monitoring
- Documentation

## Few-Shot Examples

### Example 1
**Paragraph**: "Banks shall maintain a minimum Capital to Risk-weighted Assets Ratio (CRAR) of 9% on an ongoing basis, with at least 7% in the form of Common Equity Tier 1 (CET1) capital."

**Classification**:
- para_type: "Action Para"
- has_effective_date: "No"
- effective_date: null
- business_unit: "Treasury"
- theme: "Process"
- control_object_name: "Compliance Monitoring"
- level_1: "Compliance"
- level_2: "Regulatory Compliance"
- level_3: "Capital Adequacy"
- actionable: "Maintain minimum CRAR of 9% with at least 7% CET1 capital on ongoing basis"

### Example 2
**Paragraph**: "Every Scheduled Commercial Bank shall maintain a minimum of 18% of its NDTL as Statutory Liquidity Ratio (SLR) in the form of approved securities."

**Classification**:
- para_type: "Action Para"
- has_effective_date: "No"
- effective_date: null
- business_unit: "Treasury"
- theme: "Process"
- control_object_name: "Compliance Monitoring"
- level_1: "Compliance"
- level_2: "Regulatory Compliance"
- level_3: "Reserve Requirements"
- actionable: "Maintain minimum SLR of 18% of NDTL in approved securities"
