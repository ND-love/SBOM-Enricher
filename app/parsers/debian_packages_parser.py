from __future__ import annotations

from pathlib import Path


INTERESTING_FIELDS = {
    "Package": "package_name",
    "Version": "version",
    "Architecture": "architecture",
    "Section": "section",
    "Filename": "filename",
    "Source": "source",
    "Depends": "depends",
    "Description": "description",
}


def parse_debian_packages_text(text: str) -> list[dict[str, str]]:
    if not text.strip():
        return []

    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = [block.strip() for block in normalized_text.split("\n\n") if block.strip()]

    packages: list[dict[str, str]] = []

    for block in blocks:
        parsed = _parse_block(block)

        package_name = parsed.get("package_name", "").strip()
        version = parsed.get("version", "").strip()

        if not package_name or not version:
            continue

        packages.append(
            {
                "package_name": package_name,
                "version": version,
                "architecture": parsed.get("architecture", "").strip(),
                "section": parsed.get("section", "").strip(),
                "filename": parsed.get("filename", "").strip(),
                "source": parsed.get("source", "").strip(),
                "depends": parsed.get("depends", "").strip(),
                "description": parsed.get("description", "").strip(),
            }
        )

    return packages


def parse_debian_packages_file(file_path: str | Path) -> list[dict[str, str]]:
    path = Path(file_path)
    text = path.read_text(encoding="utf-8")
    return parse_debian_packages_text(text)


def _parse_block(block: str) -> dict[str, str]:
    result: dict[str, str] = {}
    current_field: str | None = None

    for line in block.split("\n"):
        if not line.strip():
            continue

        if line.startswith((" ", "\t")) and current_field:
            result[current_field] = result.get(current_field, "") + "\n" + line.strip()
            continue

        if ":" not in line:
            current_field = None
            continue

        raw_key, raw_value = line.split(":", 1)
        raw_key = raw_key.strip()
        raw_value = raw_value.strip()

        mapped_key = INTERESTING_FIELDS.get(raw_key)
        if not mapped_key:
            current_field = None
            continue

        result[mapped_key] = raw_value
        current_field = mapped_key

    return result