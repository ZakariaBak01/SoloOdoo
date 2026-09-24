# EL MOKRIF Odoo 17 Live UI UAT

**Environment:** isolated `soloodoo_uat_ui` at `http://localhost:8070`  
**Method:** rendered Odoo UI through Chromium. No production database is used.

| Workflow | Module | Persona | UI scenario | Expected | Actual | Result | Evidence | Issue / fix |
|---|---|---|---|---|---|---|---|---|
| UAT-00 | All custom modules | U1-U14 | Login, menus and company isolation | Role-specific UI and records only | Pending setup | UNEXECUTED | — | — |
| UAT-01 | elmokrif_chantier | U1,U2,U14 | Create, validate, approve, initialize and access a chantier | Controlled lifecycle and isolation | Pending setup | UNEXECUTED | — | — |
| UAT-02 | elmokrif_chantier_estimation | U1,U2 | Estimate, approve, revise and approve variance | Calculations and immutable baseline | Pending setup | UNEXECUTED | — | — |
| UAT-03 | elmokrif_crm, elmokrif_calendar_bridge | U7,U14 | Qualify opportunity and create site visit | Valid context and company isolation | Pending setup | UNEXECUTED | — | — |
| UAT-04 | elmokrif_sale_chantier | U7,U8 | Ordinary and chantier quotations, follow-up and invoice | Standard and chantier flows work | Pending setup | UNEXECUTED | — | — |
| UAT-05 | elmokrif_chantier_stock, elmokrif_purchase_quality | U2,U1,U3,U4,U5 | Request, approval, transfer and procurement split | Exact traceability and approvals | Pending setup | UNEXECUTED | — | — |
| UAT-06 | elmokrif_purchase_quality | U3,U4 | RFQ, threshold approval and reapproval | Segregation and guardrails | Pending setup | UNEXECUTED | — | — |
| UAT-07 | elmokrif_purchase_quality | U5,U6 | Receipt and quality release/rejection | Release gates stock | Pending setup | UNEXECUTED | — | — |
| UAT-08 | elmokrif_stock_controls | U2,U1 | Consumption and valuation | Site stock and two-person approval | Pending setup | UNEXECUTED | — | — |
| UAT-09 | elmokrif_documents_bridge | U9,U10 | Document review, approval and revision | Evidence immutable and private | Pending setup | UNEXECUTED | — | — |
| UAT-10 | elmokrif_finance_readiness, elmokrif_finance_operations | U8 | Readiness, collection, cheque and bank import | Posting gate and controls | Pending setup | UNEXECUTED | — | — |
| UAT-11 | elmokrif_dashboard | U13,U14 | KPI dashboard and drill-down isolation | Authorized aggregates only | Pending setup | UNEXECUTED | — | — |
| UAT-12 | elmokrif_hr_extension | U11,U12 | Leave, appraisal, contract and recruitment | HR privacy and workflow | Pending setup | UNEXECUTED | — | — |
| UAT-13 | elmokrif_tender_boq | U1,U3,U4 | BOQ, tender evaluation and award | Controlled tender workflow | Pending setup | UNEXECUTED | — | — |
| UAT-14 | elmokrif_construction_control, elmokrif_integration_tests, elmokrif_browser_tests | U1,U2,U7,U14 | Controlled closeout and access regression | Guarded state changes and security | Pending setup | UNEXECUTED | — | — |
