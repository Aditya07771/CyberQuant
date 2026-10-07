"""
Registry of Indian Cybersecurity Regulations and Standards.
Provides verified statutory citations, effective dates, primary URLs,
applicability criteria, required evidence, and statutory penalty caps.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

# Authoritative Indian Regulatory Rules Registry (Version 2025.1)
INDIAN_REGULATORY_RULES: List[Dict[str, Any]] = [
    {
        "instrument_id": "CERTIN-70B-INCIDENT-REPORTING",
        "framework_name": "CERT-In",
        "provision_citation": "Directions under sub-section (6) of section 70B of IT Act, 2000 (No. 20(3)/2022-CERT-In), Direction 2(i)",
        "version": "2022.1",
        "title": "Mandatory 6-Hour Cyber Incident Reporting to CERT-In",
        "description": (
            "Any service provider, intermediary, data centre, body corporate and Government organisation "
            "shall mandatorily report specified cyber security incidents to CERT-In within 6 hours of noticing "
            "or being brought to notice of such incidents."
        ),
        "source_url": "https://www.cert-in.org.in/Directions70B.jsp",
        "jurisdiction": "IN",
        "effective_from": "2022-06-28T00:00:00Z",
        "effective_to": None,
        "verified_date": "2025-12-01T00:00:00Z",
        "reviewer_status": "verified_statutory_text",
        "statutory_penalty_max_usd": 1200.0,  # ~1 Lakh INR statutory criminal fine cap under S.70B(7)
        "statutory_currency": "INR",
        "statutory_penalty_max_inr": 100_000.0,
        "required_evidence": [
            "Incident discovery timestamp",
            "Initial incident triage report",
            "CERT-In incident reporting submission confirmation / email",
            "Root cause analysis / IoC list"
        ],
        "applicability_criteria": {
            "jurisdiction": ["IN", "GLOBAL_OPERATING_IN_INDIA"],
            "triggers": ["active_breach_detected", "ransomware_infection", "unauthorized_access"],
        },
    },
    {
        "instrument_id": "CERTIN-70B-LOG-RETENTION-180D",
        "framework_name": "CERT-In",
        "provision_citation": "Directions under Section 70B of IT Act, 2000, Direction 2(v)",
        "version": "2022.1",
        "title": "Mandatory Maintenance of ICT Logs for 180 Days within Indian Jurisdiction",
        "description": (
            "All service providers, intermediaries, data centres, and bodies corporate shall mandatorily enable "
            "and maintain logs of all their ICT systems securely for a rolling period of 180 days within the Indian jurisdiction."
        ),
        "source_url": "https://www.cert-in.org.in/Directions70B.jsp",
        "jurisdiction": "IN",
        "effective_from": "2022-06-28T00:00:00Z",
        "effective_to": None,
        "verified_date": "2025-12-01T00:00:00Z",
        "reviewer_status": "verified_statutory_text",
        "statutory_penalty_max_usd": 1200.0,
        "statutory_currency": "INR",
        "statutory_penalty_max_inr": 100_000.0,
        "required_evidence": [
            "SIEM log retention policy configuration",
            "Storage retention audit log verifying 180-day availability",
            "Data localization / residency proof for log archives"
        ],
        "applicability_criteria": {
            "jurisdiction": ["IN"],
            "required_controls": ["SIEM", "Centralized Logging", "Log Retention"],
        },
    },
    {
        "instrument_id": "DPDP-ACT-2023-SEC-8-5-SECURITY-SAFEGUARDS",
        "framework_name": "DPDP",
        "provision_citation": "Digital Personal Data Protection Act, 2023, Section 8(5) read with Schedule (Item 1)",
        "version": "2023.1",
        "title": "Reasonable Security Safeguards to Prevent Personal Data Breach",
        "description": (
            "A Data Fiduciary shall protect personal data in its possession or under its control, including in respect "
            "of any processing undertaken by it or on its behalf by a Data Processor, by taking reasonable security safeguards "
            "to prevent personal data breach."
        ),
        "source_url": "https://www.meity.gov.in/documents/act-and-policies",
        "jurisdiction": "IN",
        "effective_from": "2023-08-11T00:00:00Z",
        "effective_to": None,
        "verified_date": "2025-12-15T00:00:00Z",
        "reviewer_status": "verified_statutory_text",
        "statutory_penalty_max_usd": 30_000_000.0,  # ~250 Crore INR statutory maximum cap (Section 33 Schedule Item 1)
        "statutory_currency": "INR",
        "statutory_penalty_max_inr": 2_500_000_000.0,
        "required_evidence": [
            "Encryption of personal data at rest and in transit",
            "Role-based access control and MFA enforcement on personal data stores",
            "Regular vulnerability assessments and patch management logs",
            "Data Protection Impact Assessment (for Significant Data Fiduciaries)"
        ],
        "applicability_criteria": {
            "jurisdiction": ["IN"],
            "data_sensitivity_tiers": ["Confidential", "Restricted"],
            "processes_personal_data": True,
        },
    },
    {
        "instrument_id": "DPDP-ACT-2023-SEC-8-6-BREACH-NOTIFICATION",
        "framework_name": "DPDP",
        "provision_citation": "Digital Personal Data Protection Act, 2023, Section 8(6) read with Schedule (Item 2)",
        "version": "2023.1",
        "title": "Intimation of Personal Data Breach to DPB and Data Principals",
        "description": (
            "In the event of a personal data breach, the Data Fiduciary shall give the Data Protection Board of India "
            "and each affected Data Principal intimation of such breach in such form and manner as prescribed under DPDP Rules."
        ),
        "source_url": "https://www.meity.gov.in/documents/act-and-policies",
        "jurisdiction": "IN",
        "effective_from": "2023-08-11T00:00:00Z",
        "effective_to": None,
        "verified_date": "2025-12-15T00:00:00Z",
        "reviewer_status": "verified_statutory_text",
        "statutory_penalty_max_usd": 24_000_000.0,  # ~200 Crore INR statutory maximum cap (Section 33 Schedule Item 2)
        "statutory_currency": "INR",
        "statutory_penalty_max_inr": 2_000_000_000.0,
        "required_evidence": [
            "Record of personal data breach intimation to Data Protection Board",
            "Communication records to affected Data Principals",
            "Mitigation and containment measures implemented"
        ],
        "applicability_criteria": {
            "jurisdiction": ["IN"],
            "data_sensitivity_tiers": ["Confidential", "Restricted"],
            "triggers": ["personal_data_breach"],
        },
    },
    {
        "instrument_id": "RBI-IT-GOVERNANCE-2023-CYBER-CRISIS",
        "framework_name": "RBI",
        "provision_citation": "RBI Master Direction on Information Technology Governance, Risk, Controls and Assurance Practices, 2023, Chapter IV",
        "version": "2023.1",
        "title": "Cyber Crisis Management Plan & 2-Hour Breach Reporting to RBI CSITE",
        "description": (
            "Regulated Entities (Banks, NBFCs) shall maintain an approved Cyber Crisis Management Plan (CCMP) "
            "and mandatorily report cyber security incidents to RBI CSITE within 2 to 6 hours."
        ),
        "source_url": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx",
        "jurisdiction": "IN",
        "effective_from": "2024-04-01T00:00:00Z",
        "effective_to": None,
        "verified_date": "2025-11-20T00:00:00Z",
        "reviewer_status": "verified_statutory_text",
        "statutory_penalty_max_usd": 120_000.0,  # Section 47A Banking Regulation Act
        "statutory_currency": "INR",
        "statutory_penalty_max_inr": 10_000_000.0,
        "required_evidence": [
            "Board-approved CCMP document",
            "RBI CSITE incident reporting acknowledgement",
            "Quarterly Cyber Security Committee meeting minutes"
        ],
        "applicability_criteria": {
            "jurisdiction": ["IN"],
            "sectors": ["Banking", "Financial Services", "Fintech", "Payment Systems"],
        },
    },
    {
        "instrument_id": "SEBI-CSCRF-2024-VAPT-SOC",
        "framework_name": "SEBI",
        "provision_citation": "SEBI Cybersecurity and Cyber Resilience Framework (CSCRF) for Regulated Entities, 2024",
        "version": "2024.1",
        "title": "Mandatory 24x7 SOC Monitoring and Periodic VAPT Audits",
        "description": (
            "Qualified Regulated Entities shall maintain continuous 24x7 SOC monitoring, perform comprehensive "
            "VAPT audits at least biannually/quarterly through CERT-In empaneled auditors, and report critical "
            "vulnerabilities immediately."
        ),
        "source_url": "https://www.sebi.gov.in/legal/circulars",
        "jurisdiction": "IN",
        "effective_from": "2025-01-01T00:00:00Z",
        "effective_to": None,
        "verified_date": "2025-12-05T00:00:00Z",
        "reviewer_status": "verified_statutory_text",
        "statutory_penalty_max_usd": 300_000.0,
        "statutory_currency": "INR",
        "statutory_penalty_max_inr": 25_000_000.0,
        "required_evidence": [
            "CERT-In empaneled auditor VAPT report",
            "SOC SLA and log retention compliance certificate",
            "Closure verification report for High and Critical findings"
        ],
        "applicability_criteria": {
            "jurisdiction": ["IN"],
            "sectors": ["Capital Markets", "Securities", "Asset Management", "Brokerage"],
        },
    },
]
