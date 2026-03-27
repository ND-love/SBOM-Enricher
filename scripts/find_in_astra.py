from __future__ import annotations

import argparse

from app.db import SessionLocal
from app.repositories.catalog_repository import CatalogRepository
from app.services.catalog_lookup_service import CatalogLookupService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Поиск компонента в каталоге Astra Linux"
    )
    parser.add_argument("--name", required=True, help="Название компонента")
    parser.add_argument("--version", default="", help="Версия компонента")
    parser.add_argument("--os-version", default="1.8.0", help="Версия Astra Linux")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    db = SessionLocal()
    try:
        service = CatalogLookupService(repository=CatalogRepository())
        result = service.lookup_component(
            db,
            os_family="astra_linux",
            os_version=args.os_version,
            component_name=args.name,
            requested_version=args.version,
        )

        print(f"component:         {result['component_name']}")
        print(f"requested_version: {result['requested_version']}")
        print(f"status:            {result['status']}")
        print(f"message:           {result['message']}")
        print()

        found_versions = result.get("found_versions", [])
        if found_versions:
            print("Найденные версии:")
            for version in found_versions:
                print(f"  - {version}")
            print()

        matches = result.get("matches", [])
        if matches:
            print("Совпавшие записи:")
            for item in matches[:20]:
                print(
                    f"  - repo={item['repository_name']}, "
                    f"version={item['version_original']}, "
                    f"arch={item['architecture']}, "
                    f"filename={item['filename']}"
                )

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())