from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.parsers.debian_packages_parser import parse_debian_packages_file
from app.repositories.catalog_repository import CatalogRepository


class AstraImportService:
    def __init__(self, repository: CatalogRepository | None = None) -> None:
        self.repository = repository or CatalogRepository()

    def import_file(self, db: Session, file_path: str | Path) -> dict[str, str | int | bool]:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {path}")

        if path.suffix.lower() != ".txt":
            raise ValueError(f"Ожидался .txt файл, получено: {path.name}")

        os_family, os_version, repository_name = self._infer_source_identity(path)
        raw_packages = parse_debian_packages_file(path)
        prepared_packages = [self._prepare_package(pkg) for pkg in raw_packages]

        try:
            replaced_existing = self.repository.delete_source(
                db,
                os_family=os_family,
                os_version=os_version,
                repository_name=repository_name,
                original_filename=path.name,
            )

            source = self.repository.create_source(
                db,
                os_family=os_family,
                os_version=os_version,
                repository_name=repository_name,
                original_filename=path.name,
                saved_path=str(path.resolve()),
            )

            inserted_packages = self.repository.bulk_insert_packages(
                db,
                source_id=source.id,
                packages=prepared_packages,
            )

            db.commit()

        except Exception:
            db.rollback()
            raise

        return {
            "filename": path.name,
            "os_family": os_family,
            "os_version": os_version,
            "repository_name": repository_name,
            "saved_path": str(path.resolve()),
            "parsed_packages": len(raw_packages),
            "inserted_packages": inserted_packages,
            "replaced_existing": replaced_existing,
        }

    def _infer_source_identity(self, path: Path) -> tuple[str, str, str]:
        """
        Пример:
        1.8.0-main-main.txt -> ("astra_linux", "1.8.0", "main-main")
        1.8.0-main-non-free.txt -> ("astra_linux", "1.8.0", "main-non-free")
        """
        stem = path.stem
        parts = stem.split("-")

        if len(parts) < 2:
            return "astra_linux", "unknown", stem

        os_version = parts[0].strip()
        repository_name = "-".join(parts[1:]).strip() or "unknown"
        return "astra_linux", os_version, repository_name

    def _prepare_package(self, pkg: dict[str, str]) -> dict[str, str]:
        package_name = (pkg.get("package_name") or "").strip()
        version_original = (pkg.get("version") or "").strip()

        return {
            "package_name": package_name,
            "package_name_normalized": self._normalize_package_name(package_name),
            "version_original": version_original,
            "version_normalized": self._normalize_version(version_original),
            "architecture": (pkg.get("architecture") or "").strip(),
            "section": (pkg.get("section") or "").strip(),
            "filename": (pkg.get("filename") or "").strip(),
            "source_package": self._extract_source_package_name((pkg.get("source") or "").strip()),
            "depends": (pkg.get("depends") or "").strip(),
            "description": (pkg.get("description") or "").strip(),
        }

    @staticmethod
    def _normalize_package_name(value: str) -> str:
        normalized = value.strip().casefold()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    @staticmethod
    def _normalize_version(value: str) -> str:
        normalized = value.strip().casefold()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    @staticmethod
    def _extract_source_package_name(source_value: str) -> str:
        """
        Debian-style поле Source может выглядеть так:
        - "openssl"
        - "openssl (3.0.17-alt1)"
        """
        source_value = source_value.strip()
        if not source_value:
            return ""
        if " (" in source_value:
            return source_value.split(" (", 1)[0].strip()
        return source_value