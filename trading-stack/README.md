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
- Strategy behavior is now injectable from `skills/*.py` via `runtime/BaseStrategy`.
- Vanilmirth, Filir, and Amistr are strategy-agnostic consumers of injected logic.

## Strategy-as-a-Skill Architecture

### Current Investigation Findings
- The previous system stored behavior as JSON contracts and handoff artifacts, but had no shared strategy interface or hot-swap runtime.
- Agent role files existed (`workspace-vanilmirth`, `workspace-filir`, `workspace-amistr`) without executable strategy classes.
- Refactor target: keep JSON artifacts as outputs/contracts, move logic source into pluggable strategy skills.

### New Modular File Structure

```text
trading-stack/
  skills/
    __init__.py
    alpha_governor.py
    simple_scalp.py
  runtime/
    __init__.py
    contracts.py
    base_strategy.py
    compatibility_checker.py
    strategy_loader.py
    agents.py
    orchestrator.py
    strategy_ctl.py
    strategy_runtime.json
  contracts/
  handoff/
  protocols/
  strategy/
```

### BaseStrategy Contract (Mandatory Hooks)
- `get_signal_logic()` -> Vanilmirth gate logic
- `get_risk_filters()` -> Filir gate logic
- `get_execution_rules()` -> Amistr gate logic

Every skill class must inherit `runtime.base_strategy.BaseStrategy` and return typed runtime contracts.

### Compatibility Checke
- `runtime.compatibility_checker.check_strategy_compatibility()` validates:
  - required strategy metadata
  - return types for all mandatory hooks
  - field constraints (risk %, UTC time format, non-discretionary execution mode)
- Incompatible skills are blocked before they can go live.

### Dynamic Strategy Loading (Lif Orchestration)
- Runtime flag: `runtime/strategy_runtime.json` -> `LOAD_STRATEGY`.
- Lif orchestration process (`runtime/orchestrator.py`) loads selected skill and injects contracts into:
  - `VanilmirthAgent`
  - `FilirAgent`
  - `AmistrAgent`
- Watch mode (`--watch`) polls config and hot-reloads strategy logic without service restart.

## Hot-Swap Workflow

From `/home/lifadmin/.openclaw`:

1. List available skills:
```bash
python3 trading-stack/runtime/strategy_ctl.py list
```

2. Validate a new skill:
```bash
python3 trading-stack/runtime/strategy_ctl.py check alpha_governo
```

3. Hot-swap skill:
```bash
python3 trading-stack/runtime/strategy_ctl.py load simple_scalp
```

4. Run Lif orchestrator in watch mode (no restart needed for skill swaps):
```bash
python3 trading-stack/runtime/orchestrator.py --watch --interval 2
```

5. Check runtime status:
```bash
python3 trading-stack/runtime/strategy_ctl.py status
```

Result:
- Skill swap updates logic gates in-place.
- Agent engine stays constant.
- New strategy behavior is live after compatibility pass and re-initialization.
