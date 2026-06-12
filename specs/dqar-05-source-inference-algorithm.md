# Source-Type Inference Algorithm
**DQAR Shared Knowledge Base — Domain 3 / UC1 Pipeline**
*Version: June 2026 | Used by: UC1 Assessment App, UC4, UC5*

---

## Purpose

When a client FHIR extract carries no `meta.source` URI and no Provenance resources, the UC1 ingest pipeline cannot directly read the originating source system type. This algorithm infers source-type and source-system-id from FHIR resource structure using signals that US Core 6.1.0 conformance requires to be present.

**The inference result drives three AuditEvent extension fields:**
- `http://indicina.com/fhir/ext/source-type`
- `http://indicina.com/fhir/ext/source-system-id`
- `http://indicina.com/fhir/ext/source-inference-confidence`

**The `hedis-source-declaration` field (EXT 3) is derived from source-type via a direct vocabulary map — no inference required.**

---

## Why Inference Is Tractable in US Core

US Core 6.1.0 mandates `Observation.category` as a MUST SUPPORT element. This single design decision makes source-type inference reliable for the most clinically significant resources. The category code is the primary discriminator — it was designed exactly to tell consuming systems what kind of observation this is without parsing the code itself.

The US Core profile set is organized around this: there is not one Observation profile but many, each with a fixed category constraint. When a FHIR server produces a valid US Core Observation, it has already declared its category, which means the inference algorithm does not infer — it reads.

Inference only becomes probabilistic for Condition, Encounter, and Procedure, where the profile does not distinguish clinical from administrative origin.

---

## Priority 1 — Feed Manifest (asserted confidence)

Before applying any inference, check whether the resource can be matched to a declared feed in the client-provided feed manifest.

```python
def get_source_from_manifest(resource, feed_manifest):
    """
    Match resource to feed manifest entry.
    Returns (source_type, feed_id, confidence='asserted') or None.
    """
    filename = resource.get('_source_file')  # set by ingest pipeline
    if not feed_manifest or not filename:
        return None
    for feed in feed_manifest.get('feeds', []):
        if filename in feed.get('files', []):
            return {
                'source_type': feed['source_system_type'],
                'source_feed_id': feed['feed_id'],
                'confidence': 'asserted'
            }
    # File not declared in manifest
    return {
        'source_type': 'unknown',
        'source_feed_id': f"undeclared-{filename}",
        'confidence': 'unknown',
        'finding': 'UNDECLARED_SOURCE'  # triggers finding generation
    }
```

---

## Priority 2 — meta.source URI (asserted confidence)

```python
def get_source_from_meta(resource):
    """
    Derive source-type and feed-id from meta.source if present.
    Returns (source_type, source_system_id, confidence='asserted') or None.
    """
    meta_source = resource.get('meta', {}).get('source')
    if not meta_source:
        return None
    
    uri = meta_source.lower()
    
    # Source-type inference from URI patterns
    if any(k in uri for k in ['epic', 'cerner', 'meditech', 'allscripts', 'ehr', 'emr', 'clinical']):
        source_type = 'ehr-clinical'
    elif any(k in uri for k in ['claims', 'edw', 'adjudic', 'eob', 'billing']):
        source_type = 'administrative'
    elif any(k in uri for k in ['lab', 'quest', 'labcorp', 'pathology', 'lims']):
        source_type = 'lab'
    elif any(k in uri for k in ['pharmacy', 'pbm', 'rxclaim', 'medco', 'express-scripts']):
        source_type = 'pharmacy'
    elif any(k in uri for k in ['p2p', 'payer', 'exchange', 'pdex']):
        source_type = 'p2p'
    else:
        source_type = 'ehr-clinical'  # default assumption for unrecognized URIs
    
    import hashlib
    source_id = 'meta-' + hashlib.sha256(meta_source.encode()).hexdigest()[:12]
    
    return {
        'source_type': source_type,
        'source_feed_id': source_id,
        'source_system_id': source_id,
        'confidence': 'asserted'
    }
```

---

## Priority 3 — Resource Type Inference (high confidence)

Determinative resource types require no signal beyond `resourceType`:

```python
DETERMINATIVE_RESOURCE_TYPES = {
    'ExplanationOfBenefit': ('administrative', 'high'),
    'Claim':                ('administrative', 'high'),
    'ClaimResponse':        ('administrative', 'high'),
    'MedicationDispense':   ('pharmacy',       'high'),
    'Coverage':             ('administrative', 'high'),
}

def get_source_from_resource_type(resource):
    rt = resource.get('resourceType')
    if rt in DETERMINATIVE_RESOURCE_TYPES:
        source_type, confidence = DETERMINATIVE_RESOURCE_TYPES[rt]
        return {
            'source_type': source_type,
            'confidence': confidence,
            'inference_basis': f'resourceType={rt}'
        }
    return None
```

---

## Priority 4 — Observation Category (high confidence)

US Core 6.1.0 requires `Observation.category` as MUST SUPPORT. Reading category is not inference — it is reading a required declaration.

```python
OBSERVATION_CATEGORY_MAP = {
    'laboratory':     ('lab',          'high'),
    'vital-signs':    ('ehr-clinical', 'high'),
    'clinical-test':  ('ehr-clinical', 'high'),
    'exam':           ('ehr-clinical', 'high'),
    'survey':         ('ehr-clinical', 'high'),
    'social-history': ('ehr-clinical', 'high'),
    'activity':       ('ehr-clinical', 'high'),
    'imaging':        ('ehr-clinical', 'high'),
    'procedure':      ('ehr-clinical', 'high'),
    'therapy':        ('ehr-clinical', 'high'),
}

def get_source_from_observation_category(resource):
    if resource.get('resourceType') != 'Observation':
        return None
    categories = resource.get('category', [])
    for cat in categories:
        for coding in cat.get('coding', []):
            code = coding.get('code', '').lower()
            if code in OBSERVATION_CATEGORY_MAP:
                source_type, confidence = OBSERVATION_CATEGORY_MAP[code]
                return {
                    'source_type': source_type,
                    'confidence': confidence,
                    'inference_basis': f'Observation.category={code}'
                }
    return None
```

---

## Priority 5 — Secondary Signal Inference (medium confidence)

For Condition, Encounter, Procedure where resource type alone is not determinative.

```python
def get_source_from_secondary_signals(resource):
    rt = resource.get('resourceType')
    signals = []
    ehr_score = 0
    admin_score = 0
    
    if rt == 'Condition':
        # Code system signals
        codes = resource.get('code', {}).get('coding', [])
        systems = [c.get('system', '') for c in codes]
        has_snomed = any('snomed' in s.lower() for s in systems)
        has_icd10  = any('icd-10' in s.lower() or 'icd10' in s.lower() for s in systems)
        
        if has_snomed and not has_icd10:
            ehr_score += 2
            signals.append('SNOMED-only')
        elif has_icd10 and not has_snomed:
            admin_score += 2
            signals.append('ICD10-only')
        elif has_snomed and has_icd10:
            ehr_score += 1  # dual-coded suggests EHR with claims mapping
            signals.append('dual-coded')
        
        # verificationStatus signals
        vs = resource.get('verificationStatus', {}).get('coding', [{}])[0].get('code', '')
        if vs == 'confirmed':
            ehr_score += 2
            signals.append('verificationStatus=confirmed')
        elif not vs:
            admin_score += 1
            signals.append('verificationStatus=absent')
        
        # onset date signals
        if resource.get('onsetDateTime') or resource.get('onsetPeriod'):
            ehr_score += 1
            signals.append('onset-date-present')
        
        # recorder signals
        if resource.get('recorder'):
            ehr_score += 2
            signals.append('recorder-present')
    
    elif rt == 'Encounter':
        # Type coding system signals
        enc_types = resource.get('type', [])
        for et in enc_types:
            for coding in et.get('coding', []):
                system = coding.get('system', '').lower()
                if 'cpt' in system or 'hcpcs' in system:
                    admin_score += 2
                    signals.append('CPT-type-code')
                    break
                elif 'snomed' in system:
                    ehr_score += 2
                    signals.append('SNOMED-type-code')
                    break
        
        # Participant count signals
        participants = resource.get('participant', [])
        if len(participants) > 1:
            ehr_score += 2
            signals.append(f'{len(participants)}-participants')
        elif len(participants) == 0:
            admin_score += 1
            signals.append('no-participants')
        
        # Location signals
        if resource.get('location'):
            ehr_score += 1
            signals.append('location-present')
    
    elif rt == 'Procedure':
        codes = resource.get('code', {}).get('coding', [])
        systems = [c.get('system', '') for c in codes]
        has_snomed = any('snomed' in s.lower() for s in systems)
        has_cpt    = any('cpt' in s.lower() or 'hcpcs' in s.lower() for s in systems)
        
        if has_snomed:
            ehr_score += 2
            signals.append('SNOMED-procedure')
        if has_cpt and not has_snomed:
            admin_score += 1
            signals.append('CPT-only')
        
        if resource.get('performer'):
            ehr_score += 2
            signals.append('performer-present')
    
    else:
        return None  # resource type not handled by secondary signals
    
    # Score to source-type
    if ehr_score == 0 and admin_score == 0:
        return None
    
    if ehr_score > admin_score:
        return {
            'source_type': 'ehr-clinical',
            'confidence': 'medium',
            'inference_basis': ', '.join(signals),
            'ehr_score': ehr_score,
            'admin_score': admin_score
        }
    else:
        return {
            'source_type': 'administrative',
            'confidence': 'medium',
            'inference_basis': ', '.join(signals),
            'ehr_score': ehr_score,
            'admin_score': admin_score
        }
```

---

## Priority 6 — Topology Cluster (low confidence)

When no individual resource signals are available, group by structural fingerprint. Resources with identical fingerprints likely share origin.

```python
import hashlib
import json

def compute_topology_fingerprint(resource):
    """
    Stable fingerprint from structural properties.
    Does not include any patient data.
    """
    rt = resource.get('resourceType', '')
    
    # Code systems used
    code_systems = set()
    for coding in resource.get('code', {}).get('coding', []):
        if coding.get('system'):
            code_systems.add(coding['system'])
    
    # Identifier systems used
    id_systems = set()
    for identifier in resource.get('identifier', []):
        if identifier.get('system'):
            id_systems.add(identifier['system'])
    
    # Which key fields are present (not their values)
    field_presence = {
        'has_meta_source': bool(resource.get('meta', {}).get('source')),
        'has_recorder': bool(resource.get('recorder')),
        'has_performer': bool(resource.get('performer')),
        'has_participants': bool(resource.get('participant')),
        'has_location': bool(resource.get('location')),
        'has_onset': bool(resource.get('onsetDateTime') or resource.get('onsetPeriod')),
        'has_verification_status': bool(resource.get('verificationStatus')),
        'category_codes': sorted([
            c.get('code', '') 
            for cat in resource.get('category', [])
            for c in cat.get('coding', [])
        ]),
    }
    
    fingerprint_data = {
        'resource_type': rt,
        'code_systems': sorted(code_systems),
        'identifier_systems': sorted(id_systems),
        'field_presence': field_presence,
    }
    
    fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
    return 'topology-' + hashlib.sha256(fingerprint_str.encode()).hexdigest()[:8]


def get_source_from_topology_cluster(resource, cluster_registry):
    """
    Look up cluster registry to find if this fingerprint has been
    previously resolved to a source-type.
    """
    fingerprint = compute_topology_fingerprint(resource)
    if fingerprint in cluster_registry:
        cluster = cluster_registry[fingerprint]
        return {
            'source_type': cluster['majority_source_type'],
            'source_feed_id': fingerprint,
            'confidence': 'low',
            'inference_basis': f'topology-cluster-{fingerprint}',
            'cluster_size': cluster['count'],
        }
    # Register new cluster
    cluster_registry[fingerprint] = {
        'fingerprint': fingerprint,
        'resource_type': resource.get('resourceType'),
        'count': 1,
        'majority_source_type': 'unknown',
    }
    return {
        'source_type': 'unknown',
        'source_feed_id': fingerprint,
        'confidence': 'low',
        'inference_basis': f'new-topology-cluster-{fingerprint}',
    }
```

---

## Master Inference Function

```python
def infer_source_metadata(resource, feed_manifest=None, cluster_registry=None):
    """
    Run inference priorities in order. Return first successful result.
    Always returns a dict with source_type, source_feed_id,
    source_system_id, confidence, and inference_basis.
    """
    if cluster_registry is None:
        cluster_registry = {}
    
    # Priority 1: Feed manifest match
    result = get_source_from_manifest(resource, feed_manifest)
    if result and result['confidence'] != 'unknown':
        return _build_result(resource, result)
    
    # Priority 2: meta.source
    result = get_source_from_meta(resource)
    if result:
        return _build_result(resource, result)
    
    # Priority 3: Determinative resource type
    result = get_source_from_resource_type(resource)
    if result:
        return _build_result(resource, result)
    
    # Priority 4: Observation category (US Core MUST SUPPORT)
    result = get_source_from_observation_category(resource)
    if result:
        return _build_result(resource, result)
    
    # Priority 5: Secondary signals (Condition, Encounter, Procedure)
    result = get_source_from_secondary_signals(resource)
    if result:
        return _build_result(resource, result)
    
    # Priority 6: Topology cluster
    result = get_source_from_topology_cluster(resource, cluster_registry)
    return _build_result(resource, result)


def _build_result(resource, inferred):
    """
    Build complete source metadata result including
    hedis-source-declaration vocabulary mapping.
    """
    SOURCE_TYPE_TO_HEDIS = {
        'ehr-clinical':   'ecds-ehr',
        'administrative': 'ecds-administrative',
        'lab':            'ecds-lab',
        'pharmacy':       'ecds-pharmacy',
        'p2p':            'ecds-p2p',
        'unknown':        'ecds-unknown',
    }
    
    source_type = inferred.get('source_type', 'unknown')
    feed_id = inferred.get('source_feed_id', 'unknown')
    sys_id = inferred.get('source_system_id', feed_id)
    
    return {
        'source_type':            source_type,
        'source_system_id':       sys_id,
        'source_feed_id':         feed_id,
        'hedis_source_declaration': SOURCE_TYPE_TO_HEDIS.get(source_type, 'ecds-unknown'),
        'confidence':             inferred.get('confidence', 'unknown'),
        'inference_basis':        inferred.get('inference_basis', 'none'),
    }
```

---

## Confidence Distribution as a Finding

The proportion of resources at each confidence tier is a direct provenance maturity metric requiring no additional testing.

```sql
-- Provenance coverage report (Aidbox PostgreSQL)
SELECT
  ext_conf.value->>'valueCode'    AS confidence_tier,
  ext_src.value->>'valueCode'     AS source_type,
  ext_feed.value->>'valueString'  AS feed_id,
  COUNT(*)                        AS resource_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
FROM auditevent ae
CROSS JOIN LATERAL jsonb_array_elements(ae.resource->'extension') ext_conf
CROSS JOIN LATERAL jsonb_array_elements(ae.resource->'extension') ext_src
CROSS JOIN LATERAL jsonb_array_elements(ae.resource->'extension') ext_feed
WHERE ext_conf.value->>'url' = 
  'http://indicina.com/fhir/ext/source-inference-confidence'
AND ext_src.value->>'url' = 
  'http://indicina.com/fhir/ext/source-type'
AND ext_feed.value->>'url' = 
  'http://indicina.com/fhir/ext/source-feed-id'
GROUP BY 1, 2, 3
ORDER BY resource_count DESC;
```

### Maturity scoring

| Confidence distribution | Provenance maturity | Finding tier |
|---|---|---|
| >80% asserted | Governed — meta.source or Provenance implemented | No finding |
| 50-80% high + asserted | Adequate — resource structure signals strong | Tier 3 advisory |
| <50% high + asserted | Gap — inference-dependent | Tier 3 finding |
| >20% unknown | Material gap — MY2029 risk | Tier 3 HIGH severity |

---

## Undeclared Source Finding Template

```json
{
  "finding_id": "T3-PROV-001",
  "tier": 3,
  "domain": "Domain 3 — Data Lineage / Domain 6 — ECDS Readiness",
  "title": "Undeclared data sources in FHIR pipeline",
  "description": "N resources in the extract originate from source systems not declared in the client feed manifest. This indicates data flowing into the FHIR pipeline from systems outside the plan's documented inventory.",
  "evidence": "source-feed-id = undeclared-* in AuditEvent extension records",
  "severity": "HIGH",
  "my2029_risk": "HIGH — undeclared sources cannot be attributed in ECDS reporting",
  "remediation": "Audit the FHIR ingest pipeline to identify all upstream source systems. Update feed manifest and data governance inventory.",
  "remediation_owner": "Chief Data Officer / Data Governance function",
  "timeline": "Weeks — requires pipeline audit and governance process update"
}
```

---

## Cross-Reference

- **Framework:** DQAR Shared KB — `dqar-01-framework-summary.md` (Domain 3, Domain 6)
- **Application:** UC1 Assessment App — `dqar-06-uc1-app-technical-specification.md`
- **Use cases:** Applies to UC1, UC4 (CMS interoperability), UC5 (P2P exchange quality)
- **Partner guide:** `dqar-02-health-samurai-partner-guide.md` (Aidbox AuditEvent capabilities)
