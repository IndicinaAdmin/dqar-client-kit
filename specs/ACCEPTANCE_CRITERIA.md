# Acceptance Criteria

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
- [ ] validate-all orchestrates all 4 phases sequentially

## Testing
- [ ] 100% unit test coverage of validators/
- [ ] 100% integration test coverage of commands/
- [ ] All tests pass on Python 3.10, 3.11, 3.12
- [ ] CI/CD pipeline runs on every push
- [ ] Fixture data provided for all test scenarios

## Documentation
- [ ] All 5 phases documented with examples
- [ ] MANIFEST_SCHEMA.md complete with field reference
- [ ] UC_PROPERTIES.md covers JSON + SQL + API
- [ ] DBT_INTEGRATION.md covers detection + remediation
- [ ] README.md with quickstart
- [ ] TROUBLESHOOTING.md for common issues
- [ ] Inline code comments throughout

## Deployment
- [ ] Package publishable to PyPI
- [ ] GitHub releases created
- [ ] Installation tested on Linux, macOS, Windows
- [ ] Docker image available (optional)
