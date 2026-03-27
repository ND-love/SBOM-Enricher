from __future__ import annotations

import re


def normalize_component_name(value: str) -> str:
    normalized = (value or "").strip().casefold()
    normalized = normalized.replace("_", "-")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s*-\s*", "-", normalized)
    return normalized


def normalize_version(value: str) -> str:
    normalized = (value or "").strip().casefold()
    normalized = normalized.replace(",", ".")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"^(version|ver\.?)\s*", "", normalized)
    return normalized


def has_partial_version_overlap(requested: str, candidate: str) -> bool:
    """
    Нестрогое и потенциально сомнительное совпадение версии.
    Примеры:
    - 1.2 vs 1.2.0
    - 3.0.17 vs 3.0.17-alt1
    """
    requested_norm = normalize_version(requested)
    candidate_norm = normalize_version(candidate)

    if not requested_norm or not candidate_norm:
        return False

    if requested_norm == candidate_norm:
        return False

    return (
        candidate_norm.startswith(requested_norm)
        or requested_norm.startswith(candidate_norm)
    )