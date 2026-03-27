from __future__ import annotations

import argparse
from pathlib import Path

from app.db import SessionLocal
from app.parsers.input_docx_parser import InputDocxValidationError, parse_input_docx
from app.reporting.excel_report_builder import build_astra_excel_report
from app.repositories.catalog_repository import CatalogRepository
from app.services.catalog_lookup_service import CatalogLookupService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Сформировать Excel-отчет по проверке Word-файла против каталога Astra Linux"
    )
    parser.add_argument("--input", required=True, help="Путь к входному .docx файлу")
    parser.add_argument(
        "--output",
        default="reports/astra_report.xlsx",
        help="Путь к выходному .xlsx отчету",
    )
    parser.add_argument("--os-version", default="1.8.0", help="Версия Astra Linux")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        input_rows = parse_input_docx(args.input)
    except FileNotFoundError as exc:
        print(f"Ошибка: {exc}")
        return 1
    except ValueError as exc:
        print(f"Ошибка: {exc}")
        return 1
    except InputDocxValidationError as exc:
        print(f"Ошибка валидации: {exc}")
        return 1

    db = SessionLocal()
    try:
        service = CatalogLookupService(repository=CatalogRepository())

        report_rows: list[dict[str, object]] = []

        for input_row in input_rows:
            result = service.lookup_component(
                db,
                os_family="astra_linux",
                os_version=args.os_version,
                component_name=str(input_row["component_original"]),
                requested_version=str(input_row["version_original"]),
            )

            report_rows.append(
                {
                    "input_row": input_row,
                    "lookup_result": result,
                }
            )

        build_astra_excel_report(
            Path(args.output),
            astra_version=args.os_version,
            rows=report_rows,
        )

        print(f"Отчет сформирован: {args.output}")
        print(f"Проверено строк: {len(report_rows)}")

        counters = {
            "exact": 0,
            "different_version": 0,
            "absent": 0,
            "unresolved": 0,
        }
        for item in report_rows:
            status = str(item["lookup_result"]["status"])
            counters[status] = counters.get(status, 0) + 1

        print(f"  exact:              {counters.get('exact', 0)}")
        print(f"  different_version:  {counters.get('different_version', 0)}")
        print(f"  absent:             {counters.get('absent', 0)}")
        print(f"  unresolved:         {counters.get('unresolved', 0)}")

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())