from __future__ import annotations

import json
import re
from collections import defaultdict
from urllib.parse import parse_qs, quote, unquote

from sqlalchemy import distinct, func, select

from app.catalog_utils import version_series, version_sort_key
from app.models import CatalogPackage, CatalogSource

PROPERTY = "GOST:provided_by"
PROVIDER = "Astra Linux Special Edition"
ASTRA_PROVIDER = re.compile(r"(?<!\w)astra(?:[\s_-]+linux)?(?!\w)", re.IGNORECASE)
MAX_SIZE = 64 * 1024 * 1024


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Повторяющийся ключ JSON: {key}")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError(f"Недопустимое число JSON: {value}")


def parse_sbom(raw, *, max_size=MAX_SIZE):
    if max_size is not None and len(raw) > max_size:
        raise ValueError("Максимальный размер SBOM — 64 МиБ")
    doc = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_keys,
                     parse_constant=invalid_constant)
    if (not isinstance(doc, dict) or doc.get("bomFormat") != "CycloneDX"
            or doc.get("specVersion") not in ("1.6", "1.7")):
        raise ValueError("Ожидается CycloneDX JSON версии 1.6 или 1.7")
    if not isinstance(doc.get("components"), list):
        raise ValueError("Ожидается массив components")
    return doc


def components(doc):
    """Inventory components in document order, including nested components."""
    stack = list(reversed(doc["components"]))
    while stack:
        component = stack.pop()
        if not isinstance(component, dict) or not isinstance(component.get("name"), str):
            raise ValueError("У каждого компонента должно быть строковое имя")
        properties = component.get("properties", [])
        if not isinstance(properties, list) or any(
            not isinstance(prop, dict)
            or not isinstance(prop.get("name"), str)
            or not isinstance(prop.get("value"), str)
            for prop in properties
        ):
            raise ValueError(f"Некорректный массив properties у {component['name']}")
        children = component.get("components", [])
        if not isinstance(children, list):
            raise ValueError("Вложенное поле components должно быть массивом")
        yield component
        stack.extend(reversed(children))


def primary_astra_sources():
    return (
        CatalogSource.os_family == "astra_linux",
        ~CatalogSource.repository_name.regexp_match(r"(^|-)(base|extended|update)(-|$)"),
    )


def catalog_versions(db):
    records = db.execute(
        select(CatalogSource.os_version, func.count(distinct(CatalogPackage.package_name)))
        .join(CatalogPackage)
        .where(*primary_astra_sources())
        .group_by(CatalogSource.os_version)
    )
    return [
        {"version": version, "series": version_series(version), "count": count}
        for version, count in sorted(records, key=lambda row: version_sort_key(row[0]))
    ]


def load_catalog(db, release):
    records = (
        select(CatalogPackage.package_name, CatalogPackage.version_original,
               CatalogPackage.architecture, CatalogSource.repository_name)
        .join(CatalogSource)
        .where(CatalogSource.os_family == "astra_linux", CatalogSource.os_version == release)
    )
    catalog = defaultdict(list)
    for name, version, arch, source in db.execute(records.where(*primary_astra_sources())):
        catalog[name].append((version, arch, source))
    if not catalog:
        raise ValueError("Для выбранного снимка нет импортированных пакетов основного каталога")

    updates = defaultdict(list)
    for name, version, arch, source in db.execute(
        records.where(CatalogSource.repository_name.like("frozen-update-%"))
    ):
        if name in catalog:
            updates[name].append((version, arch, source))

    for name, versions in updates.items():
        updated_architectures = {arch for _, arch, _ in versions}
        catalog[name] = versions + [
            row for row in catalog[name] if row[1] not in updated_architectures
        ]
    return catalog


def package_rows(component, catalog):
    purl = component.get("purl")
    rows = catalog.get(component["name"], ())
    if purl is None:
        return rows
    if not isinstance(purl, str) or not purl.startswith("pkg:deb/"):
        return ()
    package, _, qualifiers = purl.split("#", 1)[0].partition("?")
    name, _, version = package.rsplit("/", 1)[-1].partition("@")
    if unquote(name) != component["name"]:
        return ()
    if version and unquote(version) != component.get("version"):
        return ()
    architecture = parse_qs(qualifiers).get("arch", [])
    if len(architecture) == 1:
        return [row for row in rows if row[1] in (architecture[0], "all")]
    return rows if not architecture else ()


def can_replace_version(component):
    # These fields can identify or attest to a specific artifact.
    references = component.get("externalReferences", [])
    return not any(component.get(field) for field in (
        "hashes", "evidence", "pedigree", "swid", "cpe", "omniborId", "swhid",
    )) and isinstance(references, list) and all(
        isinstance(ref, dict) and not ref.get("hashes") for ref in references
    )


def analyze(doc, catalog):
    signed = "signature" in doc
    inventory = list(components(doc))
    signed = signed or any("signature" in component for component in inventory)
    for index, component in enumerate(inventory):
        properties = component.get("properties", [])
        providers = [p["value"] for p in properties if p["name"] == PROPERTY]
        marked = any(ASTRA_PROVIDER.search(provider) for provider in providers)
        existing = any(provider.strip() for provider in providers)
        package_matches = package_rows(component, catalog)
        version = component.get("version")
        exact = sorted({f"{arch} · {source}" for candidate, arch, source in package_matches
                        if version and candidate == version})
        status = ("match" if exact else "version" if package_matches
                  else "invalid" if marked else "missing")
        versions = sorted({row[0] for row in package_matches})
        yield {
            "index": index, "component": component, "status": status,
            "marked": marked, "providers": providers, "exact": exact,
            "versions": versions,
            "eligible": bool(exact and not existing and not signed),
            "can_mark": not existing and not signed,
            "replacements": versions if status == "version" and not signed
            and can_replace_version(component) else [],
        }


def replace_version(component, version):
    component["version"] = version
    if purl := component.get("purl"):
        package, *suffix = re.split(r"([?#])", purl, maxsplit=1)
        prefix, name = package.rsplit("/", 1)
        encoded = quote(version, safe="-._~")
        component["purl"] = f"{prefix}/{name.split('@', 1)[0]}@{encoded}" + "".join(suffix)


def apply_selection(doc, catalog, indices, replacements=None):
    replacements = replacements or {}
    rows = {row["index"]: row for row in analyze(doc, catalog)}
    if any(type(index) is not int or index not in rows or version not in rows[index]["replacements"]
           for index, version in replacements.items()):
        raise ValueError("Выберите доступную версию из каталога Astra для этой строки")
    if any(type(index) is not int or index not in rows or not (
        rows[index]["eligible"] or (index in replacements and rows[index]["can_mark"])
    ) for index in indices):
        raise ValueError("Выберите только подтвержденные совпадения или сначала укажите версию Astra")

    for index, version in replacements.items():
        replace_version(rows[index]["component"], version)
    for index in set(indices):
        properties = rows[index]["component"].setdefault("properties", [])
        empty = next((p for p in properties if p["name"] == PROPERTY), None)
        if empty is None:
            properties.append({"name": PROPERTY, "value": PROVIDER})
        else:
            empty["value"] = PROVIDER
