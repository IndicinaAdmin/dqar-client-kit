# Dependencies

## Core (Required)
- click>=8.1.0 (CLI)
- pydantic>=2.0 (validation)
- ndjson>=0.3.1 (FHIR Bulk)
- pandas>=2.0 (data aggregation)
- requests>=2.31.0 (HTTP)
- pyyaml>=6.0 (config)
- jinja2>=3.1.0 (templates)

## Optional
- scikit-learn>=1.3.0 (Level 5 anomaly detection)
- databricks-sdk>=0.10.0 (Databricks API)
- duckdb>=0.9.0 (SQL alternative)

## Dev
- pytest>=7.0
- pytest-cov>=4.1
- black>=23.0
- ruff>=0.1.0
- mypy>=1.0
