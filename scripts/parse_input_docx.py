from __future__ import annotations

import argparse
from pathlib import Path

from app.parsers.input_docx_parser import InputDocxValidationError, parse_input_docx


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Проверка и предварительный разбор входного Word-файла разработчика"
    )
    parser.add_argument("--input", required=True, help="Путь к входному .docx файлу")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)

    try:
        records = parse_input_docx(input_path)
    except FileNotFoundError as exc:
        print(f"Ошибка: {exc}")
        return 1
    except ValueError as exc:
        print(f"Ошибка: {exc}")
        return 1
    except InputDocxValidationError as exc:
        print(f"Ошибка валидации: {exc}")
        return 1

    total_rows = len(records)
    missing_version_rows = sum(1 for row in records if row["is_version_missing"])
    missing_component_rows = sum(1 for row in records if row["is_component_missing"])

    print(f"Файл: {input_path}")
    print(f"Строк найдено: {total_rows}")
    print(f"Строк с пустой версией: {missing_version_rows}")
    print(f"Строк с пустым component: {missing_component_rows}")
    print()

    print("Первые 20 записей:")
    for row in records[:20]:
        print(
            f"  row={row['row_number']}, "
            f"component={row['component_original']!r}, "
            f"version={row['version_original']!r}, "
            f"component_missing={row['is_component_missing']}, "
            f"version_missing={row['is_version_missing']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())