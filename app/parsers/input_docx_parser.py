from __future__ import annotations

from pathlib import Path

from docx import Document

from app.normalization import normalize_component_name, normalize_version


REQUIRED_COLUMNS = ("component", "version")


class InputDocxValidationError(Exception):
    """Ошибка валидации входного Word-файла."""


def parse_input_docx(file_path: str | Path) -> list[dict[str, object]]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    if path.suffix.lower() != ".docx":
        raise ValueError(f"Ожидался .docx файл, получено: {path.name}")

    document = Document(path)

    if not document.tables:
        raise InputDocxValidationError("Во входном Word-файле не найдено ни одной таблицы")

    if len(document.tables) != 1:
        raise InputDocxValidationError(
            f"Ожидалась ровно одна таблица, найдено: {len(document.tables)}"
        )

    table = document.tables[0]
    if not table.rows:
        raise InputDocxValidationError("Таблица во входном Word-файле пуста")

    headers = [cell.text.strip() for cell in table.rows[0].cells]
    normalized_headers = {header.strip().casefold(): index for index, header in enumerate(headers)}

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in normalized_headers]
    if missing_columns:
        raise InputDocxValidationError(
            f"В таблице отсутствуют обязательные колонки: {', '.join(missing_columns)}"
        )

    component_idx = normalized_headers["component"]
    version_idx = normalized_headers["version"]

    results: list[dict[str, object]] = []

    for row_number, row in enumerate(table.rows[1:], start=2):
        cells = row.cells

        component_original = cells[component_idx].text.strip() if len(cells) > component_idx else ""
        version_original = cells[version_idx].text.strip() if len(cells) > version_idx else ""

        if not component_original and not version_original:
            continue

        if not component_original:
            results.append(
                {
                    "row_number": row_number,
                    "component_original": "",
                    "component_normalized": "",
                    "version_original": version_original,
                    "version_normalized": normalize_version(version_original),
                    "is_component_missing": True,
                    "is_version_missing": not bool(version_original.strip()),
                }
            )
            continue

        results.append(
            {
                "row_number": row_number,
                "component_original": component_original,
                "component_normalized": normalize_component_name(component_original),
                "version_original": version_original,
                "version_normalized": normalize_version(version_original),
                "is_component_missing": False,
                "is_version_missing": not bool(version_original.strip()),
            }
        )

    if not results:
        raise InputDocxValidationError("После разбора таблицы не найдено ни одной содержательной строки")

    return results