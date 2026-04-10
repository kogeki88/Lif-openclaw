from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from .agents import AgentFleet
from .compatibility_checker import CompatibilityReport, check_strategy_compatibility
from .contracts import StrategyBundle
from .strategy_loader import (
    RUNTIME_CONFIG_PATH,
    StrategyLoadError,
    load_strategy,
    read_runtime_config,
    set_loaded_strategy,
)

STATUS_PATH = Path(__file__).resolve().with_name("orchestrator_state.json")


@dataclass
class StrategyOrchestrator:
    fleet: AgentFleet
    current_strategy_name: Optional[str] = None
    current_bundle: Optional[StrategyBundle] = None
    current_report: Optional[CompatibilityReport] = None
    last_config_mtime: float = 0.0

    @classmethod
    def create(cls) -> "StrategyOrchestrator":
        return cls(fleet=AgentFleet.default())

    def initialize(self, strategy_name: Optional[str] = None) -> CompatibilityReport:
        strategy = load_strategy(strategy_name)
        report = check_strategy_compatibility(strategy)
        if not report.valid:
            self.current_report = report
            self._write_state()
            message = "; ".join(report.errors) if report.errors else "Unknown compatibility error."
            raise StrategyLoadError(f"Strategy compatibility failed: {message}")

        self.current_bundle = self.fleet.inject(strategy)
        self.current_report = report
        self.current_strategy_name = self.current_bundle.strategy_name
        self._update_config_mtime()
        self._write_state()
        return report

    def hot_swap(self, strategy_name: str) -> CompatibilityReport:
        set_loaded_strategy(strategy_name)
        return self.initialize(strategy_name)

    def reload_if_config_changed(self) -> Optional[CompatibilityReport]:
        if not RUNTIME_CONFIG_PATH.exists():
            return None
        mtime = RUNTIME_CONFIG_PATH.stat().st_mtime
        if mtime <= self.last_config_mtime:
            return None

        runtime_config = read_runtime_config()
        selected = str(runtime_config.get("LOAD_STRATEGY", "alpha_governor"))
        return self.initialize(selected)

    def snapshot(self) -> Dict[str, object]:
        return {
            "timestampUtc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "currentStrategyName": self.current_strategy_name,
            "currentStrategyId": self.current_bundle.strategy_id if self.current_bundle else None,
            "currentStrategyVersion": self.current_bundle.strategy_version if self.current_bundle else None,
            "compatibility": self.current_report.to_dict() if self.current_report else None,
            "agents": self.fleet.snapshot(),
        }

    def _update_config_mtime(self) -> None:
        self.last_config_mtime = RUNTIME_CONFIG_PATH.stat().st_mtime if RUNTIME_CONFIG_PATH.exists() else 0.0

    def _write_state(self) -> None:
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with STATUS_PATH.open("w", encoding="utf-8") as f:
            json.dump(self.snapshot(), f, indent=2, sort_keys=True)
            f.write("\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lif strategy orchestrator runtime")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch runtime config and hot-reload strategy when LOAD_STRATEGY changes.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Polling interval in seconds for --watch mode (defaults to AUTO_RELOAD_SECONDS in config).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    orchestrator = StrategyOrchestrator.create()
    orchestrator.initialize()
    print(json.dumps(orchestrator.snapshot(), indent=2, sort_keys=True))

    if not args.watch:
        return 0

    config = read_runtime_config()
    interval = float(args.interval or config.get("AUTO_RELOAD_SECONDS", 2))
    interval = max(0.5, interval)

    while True:
        report = orchestrator.reload_if_config_changed()
        if report:
            print(
                f"[hot-swap] {datetime.now(timezone.utc).isoformat()} "
                f"strategy={report.strategy_name} valid={report.valid}"
            )
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
