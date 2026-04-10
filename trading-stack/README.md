# Trading Stack Contracts - Strategy-as-a-Skill

This stack is strategy-agnostic by design. Strategy logic is loaded from skill modules and injected into role-specific agents at runtime.

## Operational Chain (Generic, Role-Specific)

1. Lif (orchestrator) selects `LOAD_STRATEGY`, validates compatibility, and injects the skill.
2. Vanilmirth (quant) consumes `get_signal_logic()` and publishes validation/risk authority artifacts.
3. Filir (scout) consumes `get_risk_filters()` and emits entry alerts only when required filters pass.
4. Amistr (execution/risk) consumes `get_execution_rules()` and executes only when all active gates allow it.

## Core Files

- Runtime engine:
  - `runtime/base_strategy.py`
  - `runtime/contracts.py`
  - `runtime/compatibility_checker.py`
  - `runtime/strategy_loader.py`
  - `runtime/agents.py`
  - `runtime/orchestrator.py`
  - `runtime/strategy_ctl.py`
  - `runtime/strategy_runtime.json`
- Strategy skills:
  - `skills/*.py` (each file is a standalone strategy plugin)
- Contracts and outputs:
  - `contracts/entry_alert.schema.json`
  - `contracts/validated_risk_profile.schema.json`
  - `handoff/vanilmirth/*`
  - `handoff/filir/*`
  - `handoff/amistr/*`
- Optional protocol/legacy references:
  - `protocols/*.mapping.json`
  - `strategy/strategy.json`

## BaseStrategy Interface (Mandatory Hooks)

Every strategy skill must inherit `runtime.base_strategy.BaseStrategy` and implement:

- `get_signal_logic()`
- `get_risk_filters()`
- `get_execution_rules()`

These hooks are required for injection into Vanilmirth, Filir, and Amistr.

## Compatibility Checker

`runtime.compatibility_checker.check_strategy_compatibility()` verifies:

- required metadata (`strategy_name`, `strategy_id`, `strategy_version`)
- required return types for all hooks
- guardrail constraints (risk values, UTC time format, non-discretionary mode)

If validation fails, strategy activation is blocked.

## Dynamic Loading and Hot-Swap

- Active strategy is controlled by `runtime/strategy_runtime.json` -> `LOAD_STRATEGY`.
- `runtime/orchestrator.py` initializes agents from the selected skill.
- In watch mode, orchestration hot-reloads strategy changes without process restart.

## Hot-Swap Workflow

From `/home/lifadmin/.openclaw`:

1. List available skills:
```bash
python3 trading-stack/runtime/strategy_ctl.py list
```

2. Validate a skill before activation:
```bash
python3 trading-stack/runtime/strategy_ctl.py check <skill_name>
```

3. Hot-swap strategy:
```bash
python3 trading-stack/runtime/strategy_ctl.py load <skill_name>
```

4. Run orchestrator in watch mode (continuous hot-reload):
```bash
python3 trading-stack/runtime/orchestrator.py --watch --interval 2
```

5. Inspect runtime state:
```bash
python3 trading-stack/runtime/strategy_ctl.py status
```

## Design Rule

- Agent engine stays constant.
- Strategy logic is replaceable.
- Role boundaries remain fixed (Vanilmirth/Filir/Amistr).
- Swapping skills changes behavior, not infrastructure.
