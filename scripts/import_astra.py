from __future__ import annotations

from app.config import ASTRA_RAW_DIR, ensure_directories
from app.db import SessionLocal, engine
from app.models import Base
from app.repositories.catalog_repository import CatalogRepository
from app.services.astra_import_service import AstraImportService


def main() -> int:
    ensure_directories()
    Base.metadata.create_all(bind=engine)

    files = sorted(ASTRA_RAW_DIR.glob("*.txt"))
    if not files:
        print(f"В папке нет .txt файлов: {ASTRA_RAW_DIR}")
        return 1

    repository = CatalogRepository()
    service = AstraImportService(repository=repository)

    print(f"Найдены файлы Astra: {len(files)}")
    print(f"Каталог: {ASTRA_RAW_DIR}")
    print()

    db = SessionLocal()
    total_inserted = 0

    try:
        for file_path in files:
            result = service.import_file(db, file_path)

            print(f"Файл: {result['filename']}")
            print(f"  os_family:         {result['os_family']}")
            print(f"  os_version:        {result['os_version']}")
            print(f"  repository_name:   {result['repository_name']}")
            print(f"  parsed_packages:   {result['parsed_packages']}")
            print(f"  inserted_packages: {result['inserted_packages']}")
            print(f"  replaced_existing: {result['replaced_existing']}")
            print()

            total_inserted += int(result["inserted_packages"])

        total_packages = repository.get_total_package_count(db)
        total_unique_names = repository.get_total_unique_package_names(db)
        total_sources = repository.get_total_source_count(db)

        print("Итог:")
        print(f"  обработано источников:         {total_sources}")
        print(f"  вставлено пакетов за прогон:   {total_inserted}")
        print(f"  всего пакетов в каталоге:      {total_packages}")
        print(f"  уникальных package_name:       {total_unique_names}")

    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())