from __future__ import annotations

import argparse

from app.db import SessionLocal
from app.repositories.catalog_repository import CatalogRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Поиск по каталогу Astra Linux"
    )
    parser.add_argument("--query", required=True, help="Подстрока для поиска")
    parser.add_argument("--os-version", default="1.8.0", help="Версия Astra Linux")
    parser.add_argument("--limit", type=int, default=30, help="Максимум строк вывода")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    db = SessionLocal()
    try:
        repository = CatalogRepository()
        rows = repository.search_packages(
            db,
            os_family="astra_linux",
            os_version=args.os_version,
            query=args.query,
            limit=args.limit,
        )

        print(f"query:      {args.query}")
        print(f"os_version: {args.os_version}")
        print(f"found:      {len(rows)}")
        print()

        for item in rows:
            print(
                f"- package={item['package_name']}, "
                f"version={item['version_original']}, "
                f"arch={item['architecture']}, "
                f"repo={item['repository_name']}, "
                f"section={item['section']}, "
                f"source={item['source_package']}, "
                f"filename={item['filename']}"
            )

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())