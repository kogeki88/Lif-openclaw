from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path


HOME = Path(os.environ.get("HOME", str(Path.home()))).resolve()
STATE_DIR = Path(os.environ.get("OPENCLAW_STATE_DIR", str(HOME / ".openclaw"))).resolve()
CONFIG_PATH = Path(
    os.environ.get("OPENCLAW_CONFIG_PATH", str(STATE_DIR / "openclaw.json"))
).resolve()
WORKSPACE = str((STATE_DIR / "workspace-shelter").resolve())
AGENT_DIR = str((STATE_DIR / "agents" / "shelter" / "agent").resolve())

# Shelter default model (OpenRouter).
PRIMARY_MODEL = "openrouter/gryphe/mythomax-l2-13b"
FALLBACKS = [
    "openrouter/deepseek/deepseek-r1",
]


def now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def main() -> None:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config: {CONFIG_PATH}")

    backup_path = CONFIG_PATH.parent / f"openclaw.json.shelter-backup-{now_stamp()}"
    shutil.copy2(CONFIG_PATH, backup_path)

    cfg = json.loads(CONFIG_PATH.read_text())
    agents = cfg.setdefault("agents", {})
    agent_list = agents.setdefault("list", [])

    shelter_entry = {
        "id": "shelter",
        "name": "Shelter",
        "workspace": WORKSPACE,
        "agentDir": AGENT_DIR,
        "model": {"primary": PRIMARY_MODEL, "fallbacks": FALLBACKS},
    }

    found = False
    for item in agent_list:
        if item.get("id") == "shelter":
            item.update(shelter_entry)
            found = True
            break

    if not found:
        agent_list.append(shelter_entry)

    meta = cfg.setdefault("meta", {})
    meta["lastTouchedVersion"] = "2026.4.9"
    meta["lastTouchedAt"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

    Path(WORKSPACE, "memory").mkdir(parents=True, exist_ok=True)
    Path(WORKSPACE, "logs").mkdir(parents=True, exist_ok=True)
    Path(AGENT_DIR).mkdir(parents=True, exist_ok=True)

    print(f"Updated {CONFIG_PATH}")
    print(f"Backup: {backup_path}")
    print("Shelter agent configured.")


if __name__ == "__main__":
    main()
