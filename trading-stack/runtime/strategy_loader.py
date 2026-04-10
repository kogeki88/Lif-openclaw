from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Optional, Type

from .base_strategy import BaseStrategy

ROOT_DIR = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT_DIR / "skills"
RUNTIME_CONFIG_PATH = Path(__file__).resolve().with_name("strategy_runtime.json")

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


class StrategyLoadError(RuntimeError):
    pass


def read_runtime_config() -> Dict[str, Any]:
    if not RUNTIME_CONFIG_PATH.exists():
        return {"LOAD_STRATEGY": "alpha_governor", "AUTO_RELOAD_SECONDS": 2}
    with RUNTIME_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_runtime_config(config: Dict[str, Any]) -> None:
    RUNTIME_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RUNTIME_CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
        f.write("\n")


def set_loaded_strategy(strategy_name: str) -> Dict[str, Any]:
    config = read_runtime_config()
    config["LOAD_STRATEGY"] = strategy_name
    write_runtime_config(config)
    return config


def get_loaded_strategy_name() -> str:
    return str(read_runtime_config().get("LOAD_STRATEGY", "alpha_governor"))


def _load_skill_module(skill_name: str) -> ModuleType:
    skill_path = SKILLS_DIR / f"{skill_name}.py"
    if not skill_path.exists():
        raise StrategyLoadError(f"Skill file not found: {skill_path}")

    module_name = f"skill_{skill_name}"
    spec = importlib.util.spec_from_file_location(module_name, skill_path)
    if spec is None or spec.loader is None:
        raise StrategyLoadError(f"Failed to create import spec for skill '{skill_name}'.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


def _discover_strategy_class(module: ModuleType) -> Type[BaseStrategy]:
    strategy_type: Optional[Type[BaseStrategy]] = None
    for value in vars(module).values():
        if isinstance(value, type) and issubclass(value, BaseStrategy) and value is not BaseStrategy:
            strategy_type = value
            break

    if strategy_type is None:
        raise StrategyLoadError("No BaseStrategy subclass found in skill module.")
    return strategy_type


def load_strategy(strategy_name: Optional[str] = None) -> BaseStrategy:
    selected = strategy_name or get_loaded_strategy_name()
    module = _load_skill_module(selected)
    strategy_cls = _discover_strategy_class(module)
    return strategy_cls()
