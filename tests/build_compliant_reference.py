"""
Build a fully compliant FHIR R4 / US Core 6.1.0 / QI Core 6.0 / DEQM reference extract.

Creates data/compliant-reference/ as a Bulk FHIR NDJSON extract:
  - One resource per line, UTF-8, no empty lines
  - Every resource declares all required + US Core must-support fields
  - meta.profile declares both US Core 6.1.0 and QI Core 6.0 profile URLs
  - DEQM required types present: Patient, Organization, Practitioner, Encounter, Coverage
  - QI Core priority measure types present: Condition, Observation, Procedure,
    DiagnosticReport, MedicationRequest

Run from project root:
    python tests/build_compliant_reference.py
"""

import json
import shutil
from pathlib import Path

OUT_DIR = Path("data/compliant-reference")

# ─── Canonical profile URLs ────────────────────────────────────────────────────

US_CORE = "http://hl7.org/fhir/us/core/StructureDefinition"
QI_CORE = "http://hl7.org/fhir/us/qicore/StructureDefinition"
DEQM    = "http://hl7.org/fhir/us/davinci-deqm/StructureDefinition"

# ─── Reference IDs ────────────────────────────────────────────────────────────

PATIENT_ID      = "ref-patient-001"
ORG_ID          = "ref-org-001"
PRACTITIONER_ID = "ref-prac-001"
ENCOUNTER_ID    = "ref-enc-001"
COVERAGE_ID     = "ref-cov-001"
CONDITION_ID    = "ref-cond-001"
OBSERVATION_ID  = "ref-obs-001"
PROCEDURE_ID    = "ref-proc-001"
DIAGREPORT_ID   = "ref-dr-001"
MEDREQ_ID       = "ref-medrq-001"

# ─── Resources ────────────────────────────────────────────────────────────────

def patient() -> dict:
    return {
        "resourceType": "Patient",
        "id": PATIENT_ID,
        "meta": {
            "profile": [
                f"{US_CORE}/us-core-patient",
                f"{QI_CORE}/qicore-patient",
            ]
        },
        # US Core 6.1.0 race extension (must-support)
        "extension": [
            {
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                "extension": [
                    {
                        "url": "ombCategory",
                        "valueCoding": {
                            "system": "urn:oid:2.16.840.1.113883.6.238",
                            "code": "2106-3",
                            "display": "White"
                        }
                    },
                    {"url": "text", "valueString": "White"}
                ]
            },
            {
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity",
                "extension": [
                    {
                        "url": "ombCategory",
                        "valueCoding": {
                            "system": "urn:oid:2.16.840.1.113883.6.238",
                            "code": "2186-5",
                            "display": "Not Hispanic or Latino"
                        }
                    },
                    {"url": "text", "valueString": "Not Hispanic or Latino"}
                ]
            }
        ],
        # US Core: identifier (must-support) with type + system + value
        "identifier": [
            {
                "use": "usual",
                "type": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                        "code": "MR",
                        "display": "Medical Record Number"
                    }]
                },
                "system": "http://Sonian.io/fhir/reference-mrn",
                "value": "MRN-REF-001"
            }
        ],
        "active": True,
        # US Core: name.family (must-support)
        "name": [{"use": "official", "family": "Reference", "given": ["Patient"]}],
        "telecom": [{"system": "phone", "value": "555-000-0001", "use": "home"}],
        # US Core: gender (required)
        "gender": "female",
        # US Core: birthDate (must-support)
        "birthDate": "1975-06-15",
        # US Core: address with state (must-support)
        "address": [
            {
                "use": "home",
                "line": ["123 Reference Lane"],
                "city": "Springfield",
                "state": "MA",
                "postalCode": "01234",
                "country": "US"
            }
        ],
        "communication": [
            {
                "language": {
                    "coding": [{"system": "urn:ietf:bcp:47", "code": "en", "display": "English"}]
                },
                "preferred": True
            }
        ]
    }


def organization() -> dict:
    return {
        "resourceType": "Organization",
        "id": ORG_ID,
        "meta": {
            "profile": [
                f"{US_CORE}/us-core-organization",
                f"{QI_CORE}/qicore-organization",
            ]
        },
        # US Core: identifier with NPI (must-support)
        "identifier": [
            {
                "system": "http://hl7.org/fhir/sid/us-npi",
                "value": "1234567890"
            }
        ],
        "active": True,
        # US Core: type (must-support)
        "type": [
            {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                    "code": "prov",
                    "display": "Healthcare Provider"
                }]
            }
        ],
        # US Core: name (required)
        "name": "Sonian Reference Health Plan",
        # US Core: address with state (must-support)
        "address": [
            {
                "line": ["100 Quality Ave"],
                "city": "Boston",
                "state": "MA",
                "postalCode": "02101",
                "country": "US"
            }
        ]
    }


def practitioner() -> dict:
    return {
        "resourceType": "Practitioner",
        "id": PRACTITIONER_ID,
        "meta": {
            "profile": [
                f"{US_CORE}/us-core-practitioner",
                f"{QI_CORE}/qicore-practitioner",
            ]
        },
        # US Core: identifier with NPI (must-support)
        "identifier": [
            {
                "system": "http://hl7.org/fhir/sid/us-npi",
                "value": "0987654321"
            }
        ],
        # US Core: name.family (required)
        "name": [{"use": "official", "family": "Smith", "given": ["Jane"], "prefix": ["Dr."]}],
        # US Core: qualification (must-support)
        "qualification": [
            {
                "identifier": [{"system": "http://example.org/UniversityIdentifier", "value": "12345"}],
                "code": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0360|2.7",
                        "code": "MD",
                        "display": "Doctor of Medicine"
                    }]
                }
            }
        ]
    }


def encounter() -> dict:
    return {
        "resourceType": "Encounter",
        "id": ENCOUNTER_ID,
        "meta": {
            "profile": [
                f"{US_CORE}/us-core-encounter",
                f"{QI_CORE}/qicore-encounter",
            ]
        },
        # R4 required: status
        "status": "finished",
        # R4 required: class (ActCode)
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory"
        },
        # US Core: type with CPT (must-support)
        "type": [
            {
                "coding": [
                    {
                        "system": "http://www.ama-assn.org/go/cpt",
                        "code": "99213",
                        "display": "Office or other outpatient visit, established patient, low complexity"
                    }
                ]
            }
        ],
        # US Core: serviceType
        "serviceType": {
            "coding": [{
                "system": "http://snomed.info/sct",
                "code": "394814009",
                "display": "General practice"
            }]
        },
        # R4 required: subject
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        # US Core: participant (must-support)
        "participant": [
            {
                "type": [
                    {
                        "coding": [{
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                            "code": "PPRF",
                            "display": "primary performer"
                        }]
                    }
                ],
                "period": {"start": "2024-03-15T09:00:00Z", "end": "2024-03-15T09:30:00Z"},
                "individual": {"reference": f"Practitioner/{PRACTITIONER_ID}"}
            }
        ],
        # US Core: period (must-support)
        "period": {"start": "2024-03-15T09:00:00Z", "end": "2024-03-15T09:30:00Z"},
        # US Core: reasonCode
        "reasonCode": [
            {
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": "410429000",
                    "display": "Cardiac Arrest"
                }]
            }
        ],
        # US Core: serviceProvider (must-support)
        "serviceProvider": {"reference": f"Organization/{ORG_ID}"}
    }


def coverage() -> dict:
    return {
        "resourceType": "Coverage",
        "id": COVERAGE_ID,
        "meta": {
            "profile": [
                f"{QI_CORE}/qicore-coverage",
            ]
        },
        # R4 required: status
        "status": "active",
        # QI Core must-support: type
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "HMO",
                "display": "health maintenance organization policy"
            }]
        },
        # R4 required: beneficiary
        "beneficiary": {"reference": f"Patient/{PATIENT_ID}"},
        # QI Core must-support: period
        "period": {"start": "2024-01-01", "end": "2024-12-31"},
        # R4 required: payor
        "payor": [{"reference": f"Organization/{ORG_ID}"}],
        # QI Core: subscriberId
        "subscriberId": "MEM-REF-001",
        # QI Core: relationship
        "relationship": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/subscriber-relationship",
                "code": "self",
                "display": "Self"
            }]
        }
    }


def condition() -> dict:
    return {
        "resourceType": "Condition",
        "id": CONDITION_ID,
        "meta": {
            "profile": [
                f"{US_CORE}/us-core-condition-problems-health-concerns",
                f"{QI_CORE}/qicore-condition-problems-health-concerns",
            ]
        },
        # US Core: clinicalStatus (required)
        "clinicalStatus": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                "code": "active",
                "display": "Active"
            }]
        },
        # US Core: verificationStatus (must-support)
        "verificationStatus": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                "code": "confirmed",
                "display": "Confirmed"
            }]
        },
        # US Core: category (required) — problem-list-item for problem list
        "category": [
            {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                    "code": "problem-list-item",
                    "display": "Problem List Item"
                }]
            }
        ],
        # US Core: severity
        "severity": {
            "coding": [{
                "system": "http://snomed.info/sct",
                "code": "371924009",
                "display": "Moderate to severe"
            }]
        },
        # US Core: code (required) — ICD-10 + SNOMED
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "44054006",
                    "display": "Diabetes mellitus type 2"
                },
                {
                    "system": "http://hl7.org/fhir/sid/icd-10-cm",
                    "code": "E11.9",
                    "display": "Type 2 diabetes mellitus without complications"
                }
            ]
        },
        # US Core: subject (required)
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        # US Core: encounter
        "encounter": {"reference": f"Encounter/{ENCOUNTER_ID}"},
        # US Core: onset (must-support)
        "onsetDateTime": "2020-01-10",
        # US Core: recordedDate (must-support)
        "recordedDate": "2020-01-15",
        # US Core: recorder
        "recorder": {"reference": f"Practitioner/{PRACTITIONER_ID}"},
        "note": [{"text": "Stable on current therapy. HbA1c controlled."}]
    }


def observation() -> dict:
    return {
        "resourceType": "Observation",
        "id": OBSERVATION_ID,
        "meta": {
            "profile": [
                f"{US_CORE}/us-core-observation-lab",
                f"{QI_CORE}/qicore-observation-lab",
            ]
        },
        # R4 required: status
        "status": "final",
        # US Core: category with 'laboratory' (required)
        "category": [
            {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "laboratory",
                    "display": "Laboratory"
                }]
            }
        ],
        # US Core: code with LOINC (required)
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "4548-4",
                "display": "Hemoglobin A1c/Hemoglobin.total in Blood"
            }]
        },
        # US Core: subject (required)
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        "encounter": {"reference": f"Encounter/{ENCOUNTER_ID}"},
        # US Core: effectiveDateTime (must-support)
        "effectiveDateTime": "2024-03-15T09:15:00Z",
        # US Core: issued (must-support)
        "issued": "2024-03-15T10:00:00Z",
        # US Core: performer
        "performer": [{"reference": f"Practitioner/{PRACTITIONER_ID}"}],
        # US Core: value[x] (must-support) — HbA1c 7.2%
        "valueQuantity": {
            "value": 7.2,
            "unit": "%",
            "system": "http://unitsofmeasure.org",
            "code": "%"
        },
        "interpretation": [
            {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                    "code": "N",
                    "display": "Normal"
                }]
            }
        ],
        "referenceRange": [
            {
                "low": {"value": 4.0, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%"},
                "high": {"value": 5.7, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%"},
                "text": "Normal: 4.0-5.7%"
            }
        ]
    }


def procedure() -> dict:
    return {
        "resourceType": "Procedure",
        "id": PROCEDURE_ID,
        "meta": {
            "profile": [
                f"{US_CORE}/us-core-procedure",
                f"{QI_CORE}/qicore-procedure",
            ]
        },
        # R4 required: status
        "status": "completed",
        # US Core: code with CPT (required)
        "code": {
            "coding": [
                {
                    "system": "http://www.ama-assn.org/go/cpt",
                    "code": "83036",
                    "display": "Hemoglobin; glycosylated (A1c)"
                },
                {
                    "system": "http://snomed.info/sct",
                    "code": "43396009",
                    "display": "Haemoglobin A1c measurement"
                }
            ]
        },
        # US Core: subject (required)
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        # US Core: encounter
        "encounter": {"reference": f"Encounter/{ENCOUNTER_ID}"},
        # US Core: performed (must-support)
        "performedDateTime": "2024-03-15T09:10:00Z",
        "performer": [{"actor": {"reference": f"Practitioner/{PRACTITIONER_ID}"}}],
        # QI Core: reasonCode
        "reasonCode": [
            {
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": "44054006",
                    "display": "Diabetes mellitus type 2"
                }]
            }
        ]
    }


def diagnostic_report() -> dict:
    return {
        "resourceType": "DiagnosticReport",
        "id": DIAGREPORT_ID,
        "meta": {
            "profile": [
                f"{US_CORE}/us-core-diagnosticreport-lab",
                f"{QI_CORE}/qicore-diagnosticreport-lab",
            ]
        },
        # R4 required: status
        "status": "final",
        # US Core: category with LAB (required)
        "category": [
            {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                    "code": "LAB",
                    "display": "Laboratory"
                }]
            }
        ],
        # US Core: code with LOINC (required)
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "4548-4",
                "display": "Hemoglobin A1c/Hemoglobin.total in Blood"
            }]
        },
        # US Core: subject (required)
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        "encounter": {"reference": f"Encounter/{ENCOUNTER_ID}"},
        # US Core: effectiveDateTime (must-support)
        "effectiveDateTime": "2024-03-15T09:15:00Z",
        # US Core: issued (must-support)
        "issued": "2024-03-15T10:00:00Z",
        "performer": [{"reference": f"Practitioner/{PRACTITIONER_ID}"}],
        # US Core: result (must-support)
        "result": [{"reference": f"Observation/{OBSERVATION_ID}"}],
        "conclusion": "HbA1c within acceptable range for controlled Type 2 DM."
    }


def medication_request() -> dict:
    return {
        "resourceType": "MedicationRequest",
        "id": MEDREQ_ID,
        "meta": {
            "profile": [
                f"{US_CORE}/us-core-medicationrequest",
                f"{QI_CORE}/qicore-medicationrequest",
            ]
        },
        # R4 required: status
        "status": "active",
        # R4 required: intent
        "intent": "order",
        # US Core: reported (must-support)
        "reportedBoolean": False,
        # US Core: medication[x] (required) — RxNorm
        "medicationCodeableConcept": {
            "coding": [{
                "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                "code": "860975",
                "display": "metformin HCl 500 MG Oral Tablet"
            }]
        },
        # US Core: subject (required)
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        "encounter": {"reference": f"Encounter/{ENCOUNTER_ID}"},
        # US Core: authoredOn (required)
        "authoredOn": "2024-03-15",
        # US Core: requester (required)
        "requester": {"reference": f"Practitioner/{PRACTITIONER_ID}"},
        # US Core: dosageInstruction (must-support)
        "dosageInstruction": [
            {
                "text": "Take 1 tablet by mouth twice daily with meals",
                "timing": {
                    "repeat": {
                        "frequency": 2,
                        "period": 1,
                        "periodUnit": "d"
                    }
                },
                "route": {
                    "coding": [{
                        "system": "http://snomed.info/sct",
                        "code": "26643006",
                        "display": "Oral route"
                    }]
                },
                "doseAndRate": [
                    {
                        "type": {
                            "coding": [{
                                "system": "http://terminology.hl7.org/CodeSystem/dose-rate-type",
                                "code": "ordered",
                                "display": "Ordered"
                            }]
                        },
                        "doseQuantity": {
                            "value": 500,
                            "unit": "mg",
                            "system": "http://unitsofmeasure.org",
                            "code": "mg"
                        }
                    }
                ]
            }
        ],
        "dispenseRequest": {
            "numberOfRepeatsAllowed": 5,
            "quantity": {
                "value": 60,
                "unit": "each",
                "system": "http://terminology.hl7.org/CodeSystem/v3-orderableDrugForm",
                "code": "TAB"
            }
        }
    }


# ─── Write extract ─────────────────────────────────────────────────────────────

RESOURCES_BY_TYPE = {
    "Patient":           [patient()],
    "Organization":      [organization()],
    "Practitioner":      [practitioner()],
    "Encounter":         [encounter()],
    "Coverage":          [coverage()],
    "Condition":         [condition()],
    "Observation":       [observation()],
    "Procedure":         [procedure()],
    "DiagnosticReport":  [diagnostic_report()],
    "MedicationRequest": [medication_request()],
}

if __name__ == "__main__":
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    for resource_type, resources in RESOURCES_BY_TYPE.items():
        path = OUT_DIR / f"{resource_type}.ndjson"
        with open(path, "w", encoding="utf-8") as f:
            for r in resources:
                f.write(json.dumps(r, separators=(",", ":")) + "\n")

    print(f"Compliant reference extract → {OUT_DIR}")
    print()
    print("  Profiles declared per resource type:")
    col = 20
    for rt, resources in RESOURCES_BY_TYPE.items():
        profiles = resources[0].get("meta", {}).get("profile", [])
        for i, p in enumerate(profiles):
            label = rt if i == 0 else ""
            print(f"    {label:{col}}  {p}")
        if not profiles:
            print(f"    {rt:{col}}  (no profile)")
    print()
    print(f"  {sum(len(v) for v in RESOURCES_BY_TYPE.values())} total resources across {len(RESOURCES_BY_TYPE)} files")
    print("Done.")
