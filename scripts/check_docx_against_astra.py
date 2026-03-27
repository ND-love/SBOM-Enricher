from __future__ import annotations

import argparse

from app.db import SessionLocal
from app.parsers.input_docx_parser import InputDocxValidationError, parse_input_docx
from app.repositories.catalog_repository import CatalogRepository
from app.services.catalog_lookup_service import CatalogLookupService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Проверка входного Word-файла разработчика против каталога Astra Linux"
    )
    parser.add_argument("--input", required=True, help="Путь к входному .docx файлу")
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

        counters = {
            "exact": 0,
            "different_version": 0,
            "absent": 0,
            "unresolved": 0,
        }

        print(f"Файл: {args.input}")
        print(f"Astra Linux version: {args.os_version}")
        print(f"Проверяем строк: {len(input_rows)}")
        print()

        for row in input_rows:
            component_name = str(row["component_original"])
            requested_version = str(row["version_original"])

            result = service.lookup_component(
                db,
                os_family="astra_linux",
                os_version=args.os_version,
                component_name=component_name,
                requested_version=requested_version,
            )

            status = str(result["status"])
            counters[status] = counters.get(status, 0) + 1

            print(
                f"[row {row['row_number']}] "
                f"{component_name!r} | version={requested_version!r} | "
                f"status={status}"
            )

            if result.get("was_aliased"):
                print(
                    f"  alias: {result['component_name']!r} -> "
                    f"{result['resolved_component_name']!r}"
                )

            print(f"  message: {result['message']}")

            found_versions = result.get("found_versions", [])
            if found_versions:
                print(f"  found_versions: {', '.join(found_versions)}")

            matches = result.get("matches", [])
            for item in matches[:5]:
                print(
                    "  match:"
                    f" repo={item['repository_name']},"
                    f" version={item['version_original']},"
                    f" arch={item['architecture']},"
                    f" filename={item['filename']}"
                )

            print()

        print("Итог:")
        print(f"  exact:              {counters.get('exact', 0)}")
        print(f"  different_version:  {counters.get('different_version', 0)}")
        print(f"  absent:             {counters.get('absent', 0)}")
        print(f"  unresolved:         {counters.get('unresolved', 0)}")

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())