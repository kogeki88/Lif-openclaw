from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow direct execution: python trading-stack/runtime/strategy_ctl.py ...
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from runtime.compatibility_checker import check_strategy_compatibility
from runtime.orchestrator import STATUS_PATH, StrategyOrchestrator
from runtime.strategy_loader import (
    SKILLS_DIR,
    StrategyLoadError,
    load_strategy,
    read_runtime_config,
    set_loaded_strategy,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy control plane for Lif")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List available strategy skills.")

    check_cmd = sub.add_parser("check", help="Run compatibility checks for a skill.")
    check_cmd.add_argument("strategy", help="Skill module name in trading-stack/skills (without .py).")

    load_cmd = sub.add_parser("load", help="Hot-swap to a strategy by updating LOAD_STRATEGY.")
    load_cmd.add_argument("strategy", help="Skill module name in trading-stack/skills (without .py).")

    sub.add_parser("status", help="Show runtime config and latest orchestrator state.")
    return parser.parse_args()


def _list_skills() -> int:
    if not SKILLS_DIR.exists():
        print("No skills directory found.")
        return 1

    skills = sorted(path.stem for path in SKILLS_DIR.glob("*.py") if path.stem != "__init__")
    print(json.dumps({"skills": skills}, indent=2))
    return 0


def _check_skill(strategy_name: str) -> int:
    try:
        strategy = load_strategy(strategy_name)
    except StrategyLoadError as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
        return 1

    report = check_strategy_compatibility(strategy)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.valid else 1


def _load_skill(strategy_name: str) -> int:
    orchestrator = StrategyOrchestrator.create()
    try:
        report = orchestrator.hot_swap(strategy_name)
    except StrategyLoadError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "LOAD_STRATEGY": strategy_name,
                "valid": report.valid,
                "errors": report.errors,
                "warnings": report.warnings,
                "note": "If orchestrator is running in --watch mode, agents will reinitialize without restart.",
            },
            indent=2,
        )
    )
    return 0


def _status() -> int:
    payload = {"runtimeConfig": read_runtime_config(), "orchestratorState": None}
    if STATUS_PATH.exists():
        payload["orchestratorState"] = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    print(json.dumps(payload, indent=2))
    return 0


def main() -> int:
    args = _parse_args()
    if args.command == "list":
        return _list_skills()
    if args.command == "check":
        return _check_skill(args.strategy)
    if args.command == "load":
        set_loaded_strategy(args.strategy)
        return _load_skill(args.strategy)
    if args.command == "status":
        return _status()
    raise AssertionError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
