from __future__ import annotations

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models import CatalogPackage, CatalogSource


class CatalogRepository:
    def delete_source(
        self,
        db: Session,
        *,
        os_family: str,
        os_version: str,
        repository_name: str,
        original_filename: str,
    ) -> bool:
        existing = db.execute(
            select(CatalogSource).where(
                CatalogSource.os_family == os_family,
                CatalogSource.os_version == os_version,
                CatalogSource.repository_name == repository_name,
                CatalogSource.original_filename == original_filename,
            )
        ).scalar_one_or_none()

        if existing is None:
            return False

        db.execute(delete(CatalogPackage).where(CatalogPackage.source_id == existing.id))
        db.execute(delete(CatalogSource).where(CatalogSource.id == existing.id))
        return True

    def create_source(
        self,
        db: Session,
        *,
        os_family: str,
        os_version: str,
        repository_name: str,
        original_filename: str,
        saved_path: str,
    ) -> CatalogSource:
        source = CatalogSource(
            os_family=os_family,
            os_version=os_version,
            repository_name=repository_name,
            original_filename=original_filename,
            saved_path=saved_path,
        )
        db.add(source)
        db.flush()
        return source

    def bulk_insert_packages(
        self,
        db: Session,
        *,
        source_id: int,
        packages: list[dict[str, str]],
    ) -> int:
        prepared_objects: list[CatalogPackage] = []
        seen: set[tuple[str, str, str, str]] = set()

        for pkg in packages:
            package_name = (pkg.get("package_name") or "").strip()
            version_original = (pkg.get("version_original") or "").strip()
            architecture = (pkg.get("architecture") or "").strip()
            filename = (pkg.get("filename") or "").strip()

            if not package_name or not version_original:
                continue

            dedupe_key = (package_name, version_original, architecture, filename)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            prepared_objects.append(
                CatalogPackage(
                    source_id=source_id,
                    package_name=package_name,
                    package_name_normalized=(pkg.get("package_name_normalized") or "").strip(),
                    version_original=version_original,
                    version_normalized=(pkg.get("version_normalized") or "").strip(),
                    architecture=architecture,
                    section=(pkg.get("section") or "").strip(),
                    filename=filename,
                    source_package=(pkg.get("source_package") or "").strip(),
                    depends=(pkg.get("depends") or "").strip(),
                    description=(pkg.get("description") or "").strip(),
                )
            )

        db.add_all(prepared_objects)
        db.flush()
        return len(prepared_objects)

    def get_total_package_count(self, db: Session) -> int:
        return int(db.execute(select(func.count(CatalogPackage.id))).scalar_one())

    def get_total_unique_package_names(self, db: Session) -> int:
        return int(
            db.execute(select(func.count(func.distinct(CatalogPackage.package_name_normalized)))).scalar_one()
        )

    def get_total_source_count(self, db: Session) -> int:
        return int(db.execute(select(func.count(CatalogSource.id))).scalar_one())

    def find_packages_by_name(
        self,
        db: Session,
        *,
        os_family: str,
        os_version: str,
        package_name_normalized: str,
    ) -> list[CatalogPackage]:
        rows = db.execute(
            select(CatalogPackage)
            .join(CatalogSource, CatalogPackage.source_id == CatalogSource.id)
            .where(CatalogSource.os_family == os_family)
            .where(CatalogSource.os_version == os_version)
            .where(CatalogPackage.package_name_normalized == package_name_normalized)
            .order_by(CatalogPackage.package_name, CatalogPackage.version_original, CatalogPackage.architecture)
        ).scalars().all()
        return list(rows)

    def find_distinct_versions_by_name(
        self,
        db: Session,
        *,
        os_family: str,
        os_version: str,
        package_name_normalized: str,
    ) -> list[str]:
        rows = db.execute(
            select(func.distinct(CatalogPackage.version_original))
            .join(CatalogSource, CatalogPackage.source_id == CatalogSource.id)
            .where(CatalogSource.os_family == os_family)
            .where(CatalogSource.os_version == os_version)
            .where(CatalogPackage.package_name_normalized == package_name_normalized)
            .order_by(CatalogPackage.version_original)
        ).all()
        return [row[0] for row in rows if row[0]]

    def list_sources_for_package(
        self,
        db: Session,
        *,
        os_family: str,
        os_version: str,
        package_name_normalized: str,
    ) -> list[dict[str, str]]:
        rows = db.execute(
            select(
                CatalogSource.repository_name,
                CatalogPackage.version_original,
                CatalogPackage.architecture,
                CatalogPackage.filename,
            )
            .join(CatalogSource, CatalogPackage.source_id == CatalogSource.id)
            .where(CatalogSource.os_family == os_family)
            .where(CatalogSource.os_version == os_version)
            .where(CatalogPackage.package_name_normalized == package_name_normalized)
            .order_by(CatalogSource.repository_name, CatalogPackage.version_original, CatalogPackage.architecture)
        ).all()

        return [
            {
                "repository_name": row[0],
                "version_original": row[1],
                "architecture": row[2],
                "filename": row[3],
            }
            for row in rows
        ]

    def search_packages(
        self,
        db: Session,
        *,
        os_family: str,
        os_version: str,
        query: str,
        limit: int = 50,
    ) -> list[dict[str, str]]:
        pattern = f"%{query.strip().casefold()}%"

        rows = db.execute(
            select(
                CatalogPackage.package_name,
                CatalogPackage.version_original,
                CatalogPackage.architecture,
                CatalogPackage.section,
                CatalogPackage.source_package,
                CatalogSource.repository_name,
                CatalogPackage.filename,
            )
            .join(CatalogSource, CatalogPackage.source_id == CatalogSource.id)
            .where(CatalogSource.os_family == os_family)
            .where(CatalogSource.os_version == os_version)
            .where(
                or_(
                    CatalogPackage.package_name_normalized.like(pattern),
                    CatalogPackage.source_package.like(pattern),
                    CatalogPackage.description.like(pattern),
                )
            )
            .order_by(CatalogPackage.package_name, CatalogPackage.version_original, CatalogPackage.architecture)
            .limit(limit)
        ).all()

        return [
            {
                "package_name": row[0],
                "version_original": row[1],
                "architecture": row[2],
                "section": row[3],
                "source_package": row[4],
                "repository_name": row[5],
                "filename": row[6],
            }
            for row in rows
        ]

    def list_targets(self, db: Session) -> list[dict[str, object]]:
        rows = db.execute(
            select(
                CatalogSource.os_family,
                CatalogSource.os_version,
                func.count(func.distinct(CatalogSource.id)),
                func.count(CatalogPackage.id),
            )
            .outerjoin(CatalogPackage, CatalogPackage.source_id == CatalogSource.id)
            .group_by(CatalogSource.os_family, CatalogSource.os_version)
            .order_by(CatalogSource.os_family, CatalogSource.os_version)
        ).all()

        return [
            {
                "os_family": row[0],
                "os_version": row[1],
                "source_count": int(row[2] or 0),
                "package_count": int(row[3] or 0),
            }
            for row in rows
        ]

    def list_versions_for_family(self, db: Session, *, os_family: str) -> list[str]:
        rows = db.execute(
            select(func.distinct(CatalogSource.os_version))
            .where(CatalogSource.os_family == os_family)
            .order_by(CatalogSource.os_version)
        ).all()
        return [row[0] for row in rows if row[0]]

    def list_package_entries(
        self,
        db: Session,
        *,
        os_family: str,
        os_versions: list[str],
    ) -> list[dict[str, str]]:
        if not os_versions:
            return []

        rows = db.execute(
            select(
                CatalogSource.os_family,
                CatalogSource.os_version,
                CatalogSource.repository_name,
                CatalogPackage.package_name,
                CatalogPackage.package_name_normalized,
                CatalogPackage.version_original,
                CatalogPackage.architecture,
                CatalogPackage.filename,
            )
            .join(CatalogSource, CatalogPackage.source_id == CatalogSource.id)
            .where(CatalogSource.os_family == os_family)
            .where(CatalogSource.os_version.in_(os_versions))
            .order_by(CatalogSource.os_version, CatalogPackage.package_name, CatalogPackage.version_original)
        ).all()

        return [
            {
                "os_family": row[0],
                "os_version": row[1],
                "repository_name": row[2],
                "package_name": row[3],
                "package_name_normalized": row[4],
                "version_original": row[5],
                "architecture": row[6],
                "filename": row[7],
            }
            for row in rows
        ]

    def list_package_entries_for_target(
        self,
        db: Session,
        *,
        os_family: str,
        os_version: str,
    ) -> list[dict[str, str]]:
        return self.list_package_entries(db, os_family=os_family, os_versions=[os_version])
