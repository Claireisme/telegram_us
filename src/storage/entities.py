from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENTITIES_PATH = PROJECT_ROOT / "config" / "tracked_entities.json"
DEFAULT_ISSUERS_PATH = PROJECT_ROOT / "config" / "tracked_issuers.json"


def load_tracked_entities(path: Path = DEFAULT_ENTITIES_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_tracked_issuers(path: Path = DEFAULT_ISSUERS_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))
