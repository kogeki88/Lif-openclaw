# USER.md - VANILMIRTH CONTROL

- Owner: Sean Iglesia
- Module role: Quant validation only.
- Command priority:
1. Platform safety constraints.
2. Direct owner command.
3. Module boundaries in `AGENTS.md`.

## Acceptance Criteria
- Every strategy run produces fresh `validation_report.json`.
- Risk profile is updated only from measured results.
- No live execution logic is added here.
