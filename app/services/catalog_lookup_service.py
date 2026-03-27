from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.alias_resolver import load_component_aliases, resolve_component_alias
from app.normalization import (
    has_partial_version_overlap,
    normalize_component_name,
    normalize_version,
)
from app.repositories.catalog_repository import CatalogRepository


class CatalogLookupService:
    def __init__(
        self,
        repository: CatalogRepository | None = None,
        aliases_path: str | Path = "config/component_aliases.yml",
    ) -> None:
        self.repository = repository or CatalogRepository()
        self.aliases = load_component_aliases(aliases_path)

    def lookup_component(
        self,
        db: Session,
        *,
        os_family: str,
        os_version: str,
        component_name: str,
        requested_version: str,
    ) -> dict[str, object]:
        original_component_name = component_name
        component_name_normalized = normalize_component_name(component_name)
        requested_version_normalized = normalize_version(requested_version)

        resolved_name, was_aliased = resolve_component_alias(component_name, self.aliases)

        if not component_name_normalized:
            return {
                "status": "unresolved",
                "message": "Не указано имя компонента",
                "component_name": original_component_name,
                "resolved_component_name": "",
                "was_aliased": False,
                "requested_version": requested_version,
                "found_versions": [],
                "matches": [],
            }

        if not requested_version_normalized:
            matches = self.repository.list_sources_for_package(
                db,
                os_family=os_family,
                os_version=os_version,
                package_name_normalized=resolved_name,
            )
            return {
                "status": "unresolved",
                "message": "Не указана версия компонента для точного сравнения",
                "component_name": original_component_name,
                "resolved_component_name": resolved_name,
                "was_aliased": was_aliased,
                "requested_version": requested_version,
                "found_versions": self.repository.find_distinct_versions_by_name(
                    db,
                    os_family=os_family,
                    os_version=os_version,
                    package_name_normalized=resolved_name,
                ),
                "matches": matches,
            }

        matches = self.repository.list_sources_for_package(
            db,
            os_family=os_family,
            os_version=os_version,
            package_name_normalized=resolved_name,
        )

        if not matches:
            return {
                "status": "absent",
                "message": "Компонент не найден в каталоге",
                "component_name": original_component_name,
                "resolved_component_name": resolved_name,
                "was_aliased": was_aliased,
                "requested_version": requested_version,
                "found_versions": [],
                "matches": [],
            }

        found_versions = self.repository.find_distinct_versions_by_name(
            db,
            os_family=os_family,
            os_version=os_version,
            package_name_normalized=resolved_name,
        )

        exact_matches = [
            item for item in matches
            if normalize_version(item["version_original"]) == requested_version_normalized
        ]
        if exact_matches:
            return {
                "status": "exact",
                "message": "Найдена точная версия компонента",
                "component_name": original_component_name,
                "resolved_component_name": resolved_name,
                "was_aliased": was_aliased,
                "requested_version": requested_version,
                "found_versions": found_versions,
                "matches": exact_matches,
            }

        partial_versions = [
            version for version in found_versions
            if has_partial_version_overlap(requested_version, version)
        ]
        if partial_versions:
            return {
                "status": "unresolved",
                "message": "Есть частичное или неоднозначное совпадение версии",
                "component_name": original_component_name,
                "resolved_component_name": resolved_name,
                "was_aliased": was_aliased,
                "requested_version": requested_version,
                "found_versions": found_versions,
                "matches": matches,
            }

        return {
            "status": "different_version",
            "message": "Компонент найден, но с другой версией",
            "component_name": original_component_name,
            "resolved_component_name": resolved_name,
            "was_aliased": was_aliased,
            "requested_version": requested_version,
            "found_versions": found_versions,
            "matches": matches,
        }