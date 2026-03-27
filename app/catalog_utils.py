from __future__ import annotations

import re
from typing import Iterable


OS_FAMILY_LABELS = {
    "astra_linux": "Astra Linux",
    "alt_linux": "ALT Linux",
    "red_os": "Red OS",
}


def prettify_os_family(os_family: str) -> str:
    return OS_FAMILY_LABELS.get(os_family, os_family.replace('_', ' ').title())


def make_target_label(os_family: str, os_version: str) -> str:
    family_label = prettify_os_family(os_family)
    return f"{family_label} {os_version}".strip()


def version_sort_key(version: str) -> tuple:
    parts = re.split(r"[._-]", version or "")
    key: list[tuple[int, object]] = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.casefold()))
    return tuple(key)


def version_series(version: str) -> str:
    parts = [p for p in re.split(r"[._-]", version or "") if p]
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{parts[0]}.{parts[1]}"
    return version or ""


def sort_versions(values: Iterable[str]) -> list[str]:
    return sorted(set(values), key=version_sort_key)
