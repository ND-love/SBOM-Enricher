from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.catalog_utils import sort_versions, version_series, version_sort_key
from app.repositories.catalog_repository import CatalogRepository


class CatalogCompareService:
    def __init__(self, repository: CatalogRepository | None = None) -> None:
        self.repository = repository or CatalogRepository()

    def compare_targets(
        self,
        db: Session,
        *,
        left_family: str,
        left_version: str,
        right_family: str,
        right_version: str,
    ) -> list[dict[str, object]]:
        left_map = self._aggregate_target(db, os_family=left_family, os_version=left_version)
        right_map = self._aggregate_target(db, os_family=right_family, os_version=right_version)

        all_keys = sorted(set(left_map) | set(right_map))
        rows: list[dict[str, object]] = []

        for key in all_keys:
            left_item = left_map.get(key)
            right_item = right_map.get(key)

            left_versions = left_item["versions"] if left_item else []
            right_versions = right_item["versions"] if right_item else []
            display_name = (left_item or right_item or {}).get("display_name", key)

            if left_item and right_item:
                status = "same_version" if left_versions == right_versions else "different_version"
            elif left_item:
                status = "only_left"
            else:
                status = "only_right"

            rows.append(
                {
                    "package_name": display_name,
                    "left_versions": left_versions,
                    "right_versions": right_versions,
                    "left_repositories": left_item["repositories"] if left_item else [],
                    "right_repositories": right_item["repositories"] if right_item else [],
                    "status": status,
                }
            )

        return rows

    def build_family_matrix(
        self,
        db: Session,
        *,
        os_family: str,
        anchor_version: str,
    ) -> dict[str, object]:
        all_versions = self.repository.list_versions_for_family(db, os_family=os_family)
        series = version_series(anchor_version)
        series_versions = [v for v in all_versions if version_series(v) == series]
        series_versions = sorted(series_versions, key=version_sort_key)

        if anchor_version in series_versions:
            series_versions.remove(anchor_version)
            series_versions.insert(0, anchor_version)

        entries = self.repository.list_package_entries(db, os_family=os_family, os_versions=series_versions)

        matrix: dict[str, dict[str, object]] = {}
        for entry in entries:
            key = entry["package_name_normalized"]
            row = matrix.setdefault(
                key,
                {
                    "package_name": entry["package_name"],
                    "versions_by_os": {version: [] for version in series_versions},
                },
            )
            current = row["versions_by_os"].setdefault(entry["os_version"], [])
            current.append(entry["version_original"])

        rows: list[dict[str, object]] = []
        for key in sorted(matrix):
            item = matrix[key]
            versions_by_os = {
                version: sort_versions(item["versions_by_os"].get(version, []))
                for version in series_versions
            }
            rows.append(
                {
                    "package_name": item["package_name"],
                    "versions_by_os": versions_by_os,
                }
            )

        return {
            "series": series,
            "versions": series_versions,
            "rows": rows,
        }

    def _aggregate_target(
        self,
        db: Session,
        *,
        os_family: str,
        os_version: str,
    ) -> dict[str, dict[str, object]]:
        entries = self.repository.list_package_entries_for_target(
            db,
            os_family=os_family,
            os_version=os_version,
        )
        result: dict[str, dict[str, object]] = {}
        for entry in entries:
            key = entry["package_name_normalized"]
            bucket = result.setdefault(
                key,
                {
                    "display_name": entry["package_name"],
                    "versions": [],
                    "repositories": [],
                },
            )
            bucket["versions"].append(entry["version_original"])
            bucket["repositories"].append(entry["repository_name"])

        for bucket in result.values():
            bucket["versions"] = sort_versions(bucket["versions"])
            bucket["repositories"] = sorted(set(bucket["repositories"]))

        return result
