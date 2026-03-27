from __future__ import annotations

from pathlib import Path

import yaml

from app.normalization import normalize_component_name


def load_component_aliases(file_path: str | Path) -> dict[str, str]:
    path = Path(file_path)

    if not path.exists():
        return {}

    raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    aliases_block = raw_data.get("aliases", {})

    result: dict[str, str] = {}

    for raw_input_name, raw_target_name in aliases_block.items():
        input_name = normalize_component_name(str(raw_input_name))
        target_name = normalize_component_name(str(raw_target_name))

        if not input_name or not target_name:
            continue

        result[input_name] = target_name

    return result


def resolve_component_alias(
    component_name: str,
    aliases: dict[str, str],
) -> tuple[str, bool]:
    normalized = normalize_component_name(component_name)
    resolved = aliases.get(normalized, normalized)
    was_aliased = resolved != normalized
    return resolved, was_aliased