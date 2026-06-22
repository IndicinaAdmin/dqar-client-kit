# Phase 2-5: Data Conformance, UC Properties, dbt Lineage, Integration

---

# Phase 2: Data Conformance & Manifest Matching (Weeks 3–4)

## 2.1 Manifest Matching Validator

**File:** `client_kit/validators/manifest_matching.py`

```python
from pathlib import Path
from typing import Tuple, Optional, Dict
from fnmatch import fnmatch
import json
import ndjson

class ManifestMatcher:
    """Match FHIR resources to declared feeds (no inference)."""
    
    def __init__(self, feed_inventory: Dict, verbose=False):
        """
        Args:
            feed_inventory: Output from Phase 1 (canonical_feed_inventory.json)
            verbose: Debug logging
        """
        self.feeds = {f['feed_id']: f for f in feed_inventory['feeds']}
        self.verbose = verbose
    
    def match_resource(self, resource: Dict, filename: str = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Match resource to feed. Returns (feed_id, source_system_id) or (None, None).
        
        Tries three methods in order:
        1. meta.source.reference (FHIR resource declares its source)
        2. filename_pattern (filename matches glob)
        3. external_batch_manifest (future implementation)
        
        Returns:
            (feed_id, source_system_id) if matched
            (None, None) if no match (UNDECLARED)
        """
        
        # Method 1: meta.source.reference
        meta_source = resource.get('meta', {}).get('source', {}).get('reference')
        if meta_source:
            for feed_id, feed in self.feeds.items():
                if feed['identification_method'] == 'meta.source.reference':
                    if meta_source == feed['identification_value']:
                        return (feed_id, feed['source_system_id'])
        
        # Method 2: filename_pattern
        if filename:
            for feed_id, feed in self.feeds.items():
                if feed['identification_method'] == 'filename_pattern':
                    if fnmatch(filename, feed['identification_value']):
                        return (feed_id, feed['source_system_id'])
        
        # Method 3: external_batch_manifest
        # TODO: Implement external manifest lookup
        
        return (None, None)
```

## 2.2 Five-Level Conformance Validator

**File:** `client_kit/validators/conformance.py`

```python
from typing import Dict, List
import re

class ConformanceValidator:
    """Validate FHIR resources at five levels."""
    
    def __init__(self, profile='us-core-6.1.0', vsd_year='MY2026'):
        self.profile = profile
        self.vsd_year = vsd_year
    
    def validate_resource(self, resource: Dict, resource_type: str) -> Dict:
        """
        Validate resource across five levels.
        
        Returns:
        {
            'resource_id': '...',
            'resource_type': 'Observation',
            'level_1_vsd_conformance': 0.95,
            'level_2_profile_conformance': 0.98,
            'level_3_context_conformance': 0.87,
            'level_4_plausibility': 0.92,
            'level_5_stability': None,  # Population-level only
            'errors': [...]
        }
        """
        
        errors = []
        
        # Level 1: Terminology (value set conformance)
        level_1 = self._validate_level_1_terminology(resource, resource_type)
        
        # Level 2: FHIR Profile Conformance (US Core)
        level_2 = self._validate_level_2_profile(resource, resource_type)
        
        # Level 3: Clinical Context (encounter type, encounter exists, etc.)
        level_3 = self._validate_level_3_context(resource, resource_type)
        
        # Level 4: Clinical Plausibility (ranges, constraints)
        level_4 = self._validate_level_4_plausibility(resource, resource_type)
        
        # Level 5: Stability (population-level; computed later)
        level_5 = None
        
        return {
            'resource_id': resource.get('id'),
            'resource_type': resource_type,
            'level_1_vsd_conformance': level_1,
            'level_2_profile_conformance': level_2,
            'level_3_context_conformance': level_3,
            'level_4_plausibility': level_4,
            'level_5_stability': level_5,
            'errors': errors
        }
    
    def _validate_level_1_terminology(self, resource: Dict, resource_type: str) -> float:
        """Level 1: Are codes in NCQA value sets?"""
        # Implementation: Check coding.system and coding.code against NCQA VSD
        # Return: percentage conformance (0.0 - 1.0)
        return 0.95  # Placeholder
    
    def _validate_level_2_profile(self, resource: Dict, resource_type: str) -> float:
        """Level 2: Does resource conform to US Core profile?"""
        # Implementation: Validate against US Core R4 StructureDefinition
        return 0.98  # Placeholder
    
    def _validate_level_3_context(self, resource: Dict, resource_type: str) -> float:
        """Level 3: Clinical context (encounter type, enrollment status)?"""
        # Implementation: Check encounter.class, patient enrollment
        return 0.87  # Placeholder
    
    def _validate_level_4_plausibility(self, resource: Dict, resource_type: str) -> float:
        """Level 4: Clinical plausibility (ranges, constraints)?"""
        # Implementation: Check value ranges, implausible combinations
        return 0.92  # Placeholder
```

## 2.3 PIQI Metrics

**File:** `client_kit/validators/piqi.py`

```python
from typing import Dict

class PIQIValidator:
    """Assess data quality via PIQI dimensions."""
    
    def compute_piqi_metrics(self, conformance_results: Dict) -> Dict:
        """
        Compute four PIQI dimensions:
        - Usability: Enrollment completeness
        - Plausibility: Data constraints met
        - Comparability: No ghost PCPs
        - Stability: Population anomaly detection
        
        Returns:
        {
            'piqi_usability': 0.995,
            'piqi_plausibility': 0.998,
            'piqi_comparability': 0.987,
            'piqi_stability': 'PASS'  # or 'FAIL' if Level 5 anomaly detected
        }
        """
        
        # Usability: member enrollment completeness
        usability = self._compute_usability(conformance_results)
        
        # Plausibility: data constraint conformance
        plausibility = self._compute_plausibility(conformance_results)
        
        # Comparability: provider coverage
        comparability = self._compute_comparability(conformance_results)
        
        # Stability: population-level anomaly detection
        stability = self._compute_stability(conformance_results)
        
        return {
            'piqi_usability': usability,
            'piqi_plausibility': plausibility,
            'piqi_comparability': comparability,
            'piqi_stability': stability
        }
    
    def _compute_usability(self, results: Dict) -> float:
        # Enrollment vs. 834 member count
        return 0.995
    
    def _compute_plausibility(self, results: Dict) -> float:
        # Constraint violations
        return 0.998
    
    def _compute_comparability(self, results: Dict) -> float:
        # Provider existence check
        return 0.987
    
    def _compute_stability(self, results: Dict) -> str:
        # Anomaly detection (requires scikit-learn, Level 5 optional)
        return 'PASS'
```

## 2.4 Member Drill-Down Export

**File:** `client_kit/output/member_drilldown.py`

```python
import csv
from pathlib import Path
from typing import List, Dict

class MemberDrilldownExporter:
    """Export member-level detail for plan QA comparison."""
    
    def export_csv(self, conformance_results: Dict, output_file: str):
        """
        Export member-level data:
        - Member ID
        - Resource type
        - Qualifying codes
        - Dates
        - Conformance level scores
        
        For plan to compare against their vendor portal.
        """
        
        rows = []
        for resource_result in conformance_results.get('resources', []):
            rows.append({
                'member_id': resource_result.get('subject_id'),
                'resource_type': resource_result.get('resource_type'),
                'resource_id': resource_result.get('resource_id'),
                'code': resource_result.get('code'),
                'effective_date': resource_result.get('effective_date'),
                'level_1_conformance': resource_result.get('level_1_vsd_conformance'),
                'level_2_conformance': resource_result.get('level_2_profile_conformance'),
                'level_3_conformance': resource_result.get('level_3_context_conformance'),
                'level_4_conformance': resource_result.get('level_4_plausibility'),
            })
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [])
            writer.writeheader()
            writer.writerows(rows)
```

---

# Phase 3: UC Table Properties Output (Weeks 5–6)

## 3.1 UC Properties Models

**File:** `client_kit/models/uc_properties.py`

```python
from pydantic import BaseModel
from typing import Dict, List

class UCTableProperty(BaseModel):
    """Single UC table with its DQAR properties."""
    catalog: str
    schema: str
    table: str
    properties: Dict[str, str]

class UCPropertiesOutput(BaseModel):
    """Complete UC properties output."""
    conformance_run_id: str
    timestamp: str
    plan_name: str
    manifest_version: str
    uc_table_properties: List[UCTableProperty]
```

## 3.2 UC Properties JSON Exporter

**File:** `client_kit/output/uc_properties_json.py`

```python
import json
from pathlib import Path
from typing import Dict

class UCPropertiesJSONExporter:
    """Export UC properties as JSON (Databricks API-ready)."""
    
    def export(self, conformance_results: Dict, output_file: str):
        """
        Generate uc_table_properties.json from conformance results.
        
        Output format:
        {
            "conformance_run_id": "conf-20251014-acme-001",
            "timestamp": "2025-10-14T20:15:00Z",
            "plan_name": "Acme Health Plan",
            "manifest_version": "2.1",
            "uc_table_properties": [
                {
                    "catalog": "aidbox_catalog",
                    "schema": "fhir_stage",
                    "table": "observation",
                    "properties": {
                        "dqar.source_feed_id": "lab-vendor-x-daily-1030utc|ehr-epic-447",
                        "dqar.level_1_vsd_conformance": "0.9888",
                        ...
                    }
                }
            ]
        }
        """
        
        # Group conformance results by resource type (maps to UC table)
        table_properties = {}
        
        for result in conformance_results.get('resources', []):
            resource_type = result['resource_type']
            
            if resource_type not in table_properties:
                table_properties[resource_type] = {
                    'catalog': 'aidbox_catalog',
                    'schema': 'fhir_stage',
                    'table': resource_type.lower(),
                    'properties': {}
                }
            
            # Aggregate properties (group by feed)
            table_properties[resource_type]['properties'].update({
                f"dqar.level_1_vsd_conformance": str(result['level_1_vsd_conformance']),
                f"dqar.level_2_profile_conformance": str(result['level_2_profile_conformance']),
                f"dqar.level_3_context_conformance": str(result['level_3_context_conformance']),
                f"dqar.level_4_plausibility": str(result['level_4_plausibility']),
                f"dqar.source_feed_id": result.get('feed_id', 'UNKNOWN'),
            })
        
        output = {
            'conformance_run_id': conformance_results.get('run_id'),
            'timestamp': conformance_results.get('timestamp'),
            'plan_name': conformance_results.get('plan_name'),
            'manifest_version': conformance_results.get('manifest_version'),
            'uc_table_properties': list(table_properties.values())
        }
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
```

## 3.3 UC Properties SQL Exporter

**File:** `client_kit/output/uc_properties_sql.py`

```python
import json
from pathlib import Path
from jinja2 import Template

class UCPropertiesSQLExporter:
    """Export UC properties as SQL DDL (git-friendly IaC)."""
    
    SQL_TEMPLATE = """-- Generated by client-kit-data-conformance v2.0.0
-- Conformance run: {{ conformance_run_id }}
-- Timestamp: {{ timestamp }}
-- Plan: {{ plan_name }}
-- Manifest version: {{ manifest_version }}

-- ============================================================
-- TABLE: {{ catalog }}.{{ schema }}.{{ table }}
-- ============================================================

ALTER TABLE {{ catalog }}.{{ schema }}.{{ table }} SET TBLPROPERTIES (
{%- for key, value in properties.items() %}
    '{{ key }}' = '{{ value }}'{{ "," if not loop.last else "" }}
{%- endfor %}
);
"""
    
    def export(self, conformance_results: dict, output_file: str):
        """
        Generate uc_table_properties.sql from UC properties JSON.
        """
        
        with open(output_file, 'w') as f:
            for table_config in conformance_results.get('uc_table_properties', []):
                template = Template(self.SQL_TEMPLATE)
                sql = template.render(
                    conformance_run_id=conformance_results.get('conformance_run_id'),
                    timestamp=conformance_results.get('timestamp'),
                    plan_name=conformance_results.get('plan_name'),
                    manifest_version=conformance_results.get('manifest_version'),
                    catalog=table_config['catalog'],
                    schema=table_config['schema'],
                    table=table_config['table'],
                    properties=table_config['properties']
                )
                f.write(sql)
                f.write('\n\n')
```

---

# Phase 4: dbt Lineage Capture (Weeks 7–8)

## 4.1 dbt Manifest Parser

**File:** `client_kit/utils/dbt_parser.py`

```python
import json
from pathlib import Path
from typing import Dict, List, Optional

class dbtManifestParser:
    """Parse dbt manifest.json to extract lineage metadata."""
    
    def __init__(self, dbt_project_dir: str = '.'):
        self.project_dir = Path(dbt_project_dir)
        self.manifest_path = self.project_dir / 'target' / 'manifest.json'
        self.manifest = None
        
        if self.manifest_path.exists():
            with open(self.manifest_path) as f:
                self.manifest = json.load(f)
    
    def has_manifest(self) -> bool:
        """Check if dbt project exists."""
        return self.manifest is not None
    
    def extract_models(self) -> List[Dict]:
        """Extract all dbt models."""
        if not self.manifest:
            return []
        
        models = []
        for node_id, node in self.manifest.get('nodes', {}).items():
            if node.get('resource_type') == 'model':
                models.append({
                    'name': node.get('name'),
                    'path': node.get('path'),
                    'type': node.get('config', {}).get('materialized'),
                    'description': node.get('description'),
                    'depends_on': node.get('depends_on', {}).get('nodes', [])
                })
        
        return models
    
    def extract_sources(self) -> List[Dict]:
        """Extract all upstream sources."""
        if not self.manifest:
            return []
        
        sources = []
        for node_id, node in self.manifest.get('sources', {}).items():
            sources.append({
                'source_name': node.get('source_name'),
                'name': node.get('name'),
                'database': node.get('database'),
                'schema': node.get('schema')
            })
        
        return sources
    
    def find_hedis_relevant_models(self) -> List[Dict]:
        """Identify HEDIS-relevant models (heuristic)."""
        if not self.manifest:
            return []
        
        models = self.extract_models()
        hedis_keywords = ['hedis', 'measure', 'cohort', 'flag', 'member']
        
        return [
            m for m in models
            if any(kw in m['name'].lower() for kw in hedis_keywords)
            or m['type'] == 'mart'
        ]
```

## 4.2 Lineage Detection Validator

**File:** `client_kit/validators/lineage_detection.py`

```python
from pathlib import Path
from typing import Dict, List
from client_kit.utils.dbt_parser import dbtManifestParser

class LineageDetectionValidator:
    """Detect pre-FHIR lineage gaps (dbt without OpenLineage emission)."""
    
    def __init__(self, project_dir: str = '.', verbose: bool = False):
        self.parser = dbtManifestParser(project_dir)
        self.verbose = verbose
    
    def validate_lineage_coverage(self) -> Dict:
        """
        Detect dbt projects and emit Tier 3 findings.
        
        Returns:
        {
            'dbt_detected': True/False,
            'findings': [...]
        }
        """
        
        if not self.parser.has_manifest():
            return {'dbt_detected': False, 'findings': []}
        
        models = self.parser.extract_models()
        hedis_models = self.parser.find_hedis_relevant_models()
        sources = self.parser.extract_sources()
        
        finding = {
            'finding_id': 'pre-fhir-lineage-001',
            'tier': 3,
            'severity': 'HIGH',
            'title': 'Pre-FHIR Data Transformation Lineage Not Instrumented',
            'description': f'Detected {len(models)} dbt models ({len(hedis_models)} HEDIS-relevant) from {len(sources)} upstream sources. However, lineage is not emitted as OpenLineage events.',
            'evidence': {
                'dbt_models_count': len(models),
                'dbt_hedis_models': len(hedis_models),
                'dbt_sources_count': len(sources),
                'openlineage_emission': 'NOT DETECTED'
            },
            'impact': 'Lineage stops at dbt output tables; upstream transformation logic is unauditable.',
            'remediation': {
                'short_term': 'Install dbt-openlineage plugin',
                'long_term': 'Migrate transformations to SQL on FHIR ViewDefinitions'
            }
        }
        
        return {'dbt_detected': True, 'findings': [finding]}
```

---

# Phase 5: Integration & Orchestration (Weeks 9–10)

## 5.1 Orchestrator Command

**File:** `client_kit/commands/validate_all.py`

```python
import json
import logging
from pathlib import Path
from datetime import datetime

def run(ndjson_dir, manifest_file, output_dir, profile, vsd_year, verbose):
    """
    Orchestrate all 5 phases of UC1 assessment.
    
    Returns:
        0 = success, 1 = failure
    """
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("Starting UC1 Assessment (validate-all)")
    logger.info("=" * 80)
    
    # Phase 1: Manifest validation
    logger.info("\nPhase 1/5: Validating manifest...")
    from client_kit.commands.validate_manifest import run as phase1_run
    
    exit_code = phase1_run(
        manifest_file=manifest_file,
        output=str(output_path / 'manifest-validation-report.json'),
        canonical_feed_inventory=str(output_path / 'feed-inventory-canonical.json'),
        verbose=verbose
    )
    
    if exit_code != 0:
        logger.error("❌ Manifest validation failed. Stopping.")
        return 1
    
    logger.info("✅ Phase 1 complete")
    
    # Phase 2: Data conformance validation
    logger.info("\nPhase 2/5: Validating data conformance...")
    from client_kit.commands.validate_data import run as phase2_run
    
    exit_code = phase2_run(
        ndjson_dir=ndjson_dir,
        manifest_file=manifest_file,
        output_dir=str(output_path),
        profile=profile,
        vsd_year=vsd_year,
        sample_size=None,
        skip_level_5=False,
        verbose=verbose
    )
    
    if exit_code != 0:
        logger.error("❌ Data conformance validation failed. Stopping.")
        return 1
    
    logger.info("✅ Phase 2 complete")
    
    # Phase 3: UC properties generation
    logger.info("\nPhase 3/5: Generating UC table properties...")
    
    from client_kit.output.uc_properties_json import UCPropertiesJSONExporter
    from client_kit.output.uc_properties_sql import UCPropertiesSQLExporter
    
    conformance_file = output_path / 'conformance_report.json'
    with open(conformance_file) as f:
        conformance_results = json.load(f)
    
    json_exporter = UCPropertiesJSONExporter()
    sql_exporter = UCPropertiesSQLExporter()
    
    json_exporter.export(conformance_results, str(output_path / 'uc_table_properties.json'))
    sql_exporter.export(conformance_results, str(output_path / 'uc_table_properties.sql'))
    
    logger.info("✅ Phase 3 complete")
    
    # Phase 4: dbt lineage detection
    logger.info("\nPhase 4/5: Detecting dbt lineage gaps...")
    
    from client_kit.validators.lineage_detection import LineageDetectionValidator
    
    lineage_validator = LineageDetectionValidator('.', verbose=verbose)
    lineage_result = lineage_validator.validate_lineage_coverage()
    
    if lineage_result.get('dbt_detected'):
        logger.info("⚠️  dbt project detected. Pre-FHIR lineage gaps found.")
    
    logger.info("✅ Phase 4 complete")
    
    # Phase 5: Aggregation & reporting
    logger.info("\nPhase 5/5: Aggregating findings and generating reports...")
    
    from client_kit.output.dqar_findings import DQARFindingsAggregator
    
    findings_aggregator = DQARFindingsAggregator(
        manifest_result=str(output_path / 'manifest-validation-report.json'),
        conformance_result=str(conformance_file),
        uc_properties=str(output_path / 'uc_table_properties.json'),
        lineage_result=lineage_result if lineage_result.get('dbt_detected') else None
    )
    
    dqar_findings = findings_aggregator.aggregate()
    
    with open(output_path / 'DQAR_FINDINGS.json', 'w') as f:
        json.dump(dqar_findings, f, indent=2)
    
    logger.info("✅ Phase 5 complete")
    
    logger.info("\n" + "=" * 80)
    logger.info("UC1 ASSESSMENT COMPLETE")
    logger.info("=" * 80)
    logger.info(f"\nOutput directory: {output_path}")
    logger.info("\nKey artifacts:")
    logger.info("  - manifest-validation-report.json")
    logger.info("  - conformance_report.json")
    logger.info("  - uc_table_properties.json")
    logger.info("  - uc_table_properties.sql")
    logger.info("  - DQAR_FINDINGS.json")
    logger.info("  - EXECUTIVE_SUMMARY.html")
    logger.info("  - LOAD_INSTRUCTIONS.md")
    
    return 0
```

## 5.2 DQAR Findings Aggregator

**File:** `client_kit/output/dqar_findings.py`

```python
import json
from pathlib import Path
from typing import Dict, List, Optional

class DQARFindingsAggregator:
    """Aggregate findings from all phases into Tier 1, 2, 3."""
    
    def __init__(self, manifest_result: str, conformance_result: str, 
                 uc_properties: str, lineage_result: Optional[Dict] = None):
        self.manifest_result = manifest_result
        self.conformance_result = conformance_result
        self.uc_properties = uc_properties
        self.lineage_result = lineage_result
    
    def aggregate(self) -> Dict:
        """Aggregate all findings into Tiers 1, 2, 3."""
        
        findings_by_tier = {
            'tier_1': self._generate_tier_1_findings(),
            'tier_2': self._generate_tier_2_findings(),
            'tier_3': self._generate_tier_3_findings()
        }
        
        all_findings = (
            findings_by_tier['tier_1'] +
            findings_by_tier['tier_2'] +
            findings_by_tier['tier_3']
        )
        
        return {
            'assessment_timestamp': self._timestamp(),
            'findings_by_tier': findings_by_tier,
            'summary': {
                'tier_1_count': len(findings_by_tier['tier_1']),
                'tier_2_count': len(findings_by_tier['tier_2']),
                'tier_3_count': len(findings_by_tier['tier_3']),
                'total_findings': len(all_findings),
                'high_severity': len([f for f in all_findings if f.get('severity') == 'HIGH'])
            }
        }
    
    def _generate_tier_1_findings(self) -> List[Dict]:
        """Governance gaps from manifest."""
        
        with open(self.manifest_result) as f:
            manifest = json.load(f)
        
        findings = []
        
        if manifest.get('status') == 'FAILED':
            findings.append({
                'finding_id': 'governance-manifest-001',
                'tier': 1,
                'severity': 'HIGH',
                'title': 'Manifest Validation Failed',
                'description': 'Feed manifest contains errors',
                'errors': manifest.get('errors', [])
            })
        
        return findings
    
    def _generate_tier_2_findings(self) -> List[Dict]:
        """Data quality issues from conformance."""
        
        with open(self.conformance_result) as f:
            conformance = json.load(f)
        
        findings = []
        
        # Check conformance levels below threshold
        for level in ['level_1', 'level_2', 'level_3', 'level_4']:
            avg_score = conformance.get(f'{level}_avg', 1.0)
            if avg_score < 0.90:
                findings.append({
                    'finding_id': f'quality-{level}-002',
                    'tier': 2,
                    'severity': 'MEDIUM',
                    'title': f'{level.upper()} Conformance Below Threshold',
                    'score': avg_score,
                    'threshold': 0.90
                })
        
        return findings
    
    def _generate_tier_3_findings(self) -> List[Dict]:
        """Digital readiness gaps."""
        
        findings = []
        
        # Pre-FHIR lineage gap (from dbt detection)
        if self.lineage_result and self.lineage_result.get('dbt_detected'):
            findings.extend(self.lineage_result.get('findings', []))
        
        return findings
    
    def _timestamp(self) -> str:
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'
```

---

# DEPENDENCIES

```toml
[build-system]
requires = ["setuptools>=65.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "dqar-client-kit"
version = "2.0.0"
description = "Data quality audit readiness validation for healthcare payers"
authors = [{name = "Sonian/Indicina", email = "dev@indicina.io"}]
license = {text = "Apache 2.0"}
requires-python = ">=3.10"

dependencies = [
    "click>=8.1.0",
    "pydantic>=2.0",
    "pydantic-core",
    "ndjson>=0.3.1",
    "pandas>=2.0",
    "requests>=2.31.0",
    "pyyaml>=6.0",
    "jinja2>=3.1.0",
]

[project.optional-dependencies]
advanced = ["scikit-learn>=1.3.0"]
databricks = ["databricks-sdk>=0.10.0"]
duckdb = ["duckdb>=0.9.0"]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.1",
    "black>=23.0",
    "ruff>=0.1.0",
    "mypy>=1.0",
]

[project.scripts]
client-kit = "client_kit.cli:cli"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

# ACCEPTANCE_CRITERIA

## Build & Package
- [ ] pyproject.toml valid and installable
- [ ] `pip install .` succeeds
- [ ] `client-kit --version` works
- [ ] `client-kit --help` shows all subcommands

## Functionality
- [ ] Manifest validation: passes valid, rejects invalid
- [ ] Data conformance: all 5 levels compute correctly
- [ ] PIQI metrics: aggregated correctly
- [ ] Manifest matching: no false positives/negatives
- [ ] UC properties: JSON ↔ SQL consistent
- [ ] dbt detection: identifies projects, emits findings

## Testing
- [ ] 100% unit test coverage of validators/
- [ ] 100% integration test coverage of commands/
- [ ] All tests pass on Python 3.10, 3.11, 3.12
- [ ] CI/CD pipeline runs on every push

## Documentation
- [ ] All 5 phases documented
- [ ] MANIFEST_SCHEMA.md complete
- [ ] UC_PROPERTIES.md complete
- [ ] DBT_INTEGRATION.md complete
- [ ] README.md with quickstart
- [ ] Inline code comments throughout

---

# EXAMPLES

## Example 1: Validate Manifest

```bash
client-kit validate-manifest manifest.json \
  --output manifest-report.json \
  --canonical-feed-inventory feed-inventory.json
```

## Example 2: Validate Data

```bash
client-kit validate-data \
  ./bulk-export/ \
  manifest.json \
  --output-dir ./conformance-results \
  --profile us-core-6.1.0
```

## Example 3: Complete Assessment

```bash
client-kit validate-all \
  ./bulk-export/ \
  manifest.json \
  --output-dir ./uc1-assessment \
  --vsd-year MY2026 \
  --verbose
```

## Example 4: Load UC Properties to Databricks

```bash
python examples/load_properties_api.py \
  uc1-assessment/uc_table_properties.json \
  --workspace-url https://workspace.databricks.com \
  --token YOUR_TOKEN
```
