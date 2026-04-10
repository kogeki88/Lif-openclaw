# Trading Stack Contracts - Alpha-Governor Protocol

Operational chain:
1. Vanilmirth validates strategy viability + publishes risk authority profile.
2. Filir scans M15 Camarilla R3/S3 breakouts with H4/H1 EMA, volume, ATR, and momentum gates.
3. Amistr executes only when all layers align and all risk guards pass.

Core files:
- `strategy/strategy.json`
- `protocols/alpha-governor.mapping.json`
- `contracts/entry_alert.schema.json`
- `contracts/validated_risk_profile.schema.json`
- `handoff/vanilmirth/validation_report.json`
- `handoff/vanilmirth/validated_risk_profile.json`
- `handoff/filir/entry_alerts.jsonl`
- `handoff/filir/latest_entry_alert.json`
- `handoff/amistr/execution_log.jsonl`
- `handoff/amistr/risk_state.json`
- `handoff/amistr/open_positions.json`

Alpha-Governor hard gates:
- Signal layer: M15 Camarilla breakout + H4/H1 EMA(20/50) + Volume Z-Score > 2.0 + rising ATR.
- Momentum layer: Tier 2 risk (1.875%) allowed only when TDI slope > 30 degrees and H1 ADX > 25.
- Risk layer: dynamic throttle to 0.5% after 3 consecutive losses, 4.5% global heat cap, 3.0% USD correlation cap.
- Management layer: 0.6R breakeven trigger, sunset lock at 18:00 UTC, hard flatten at 19:55 UTC.
- Execution policy: strictly non-discretionary; if any gate fails, execution remains dormant.

Design rule:
- Strategy behavior is hard-coded in `strategy/strategy.json` and `protocols/alpha-governor.mapping.json`.
- Filir and Amistr must consume only validated artifacts and never override gates heuristically.
