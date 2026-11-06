import json
from copy import deepcopy

import pytest

from app.services.sbom_service import PROPERTY, PROVIDER, analyze, apply_selection, parse_sbom

CATALOG = {"openssl": [("1:3.0.1-astra2", "amd64", "main")]}


def component(name="openssl", version="1:3.0.1-astra2", provider=None, **extra):
    item = {"name": name, "version": version, **extra}
    if provider is not None:
        item["properties"] = [{"name": PROPERTY, "value": provider}]
    return item


def test_statuses_and_no_false_candidates():
    doc = {"components": [
        component(), component(version="3.0.1"),
        component("missing", provider=PROVIDER),
        component(version="3.0.1", provider=PROVIDER),
        component(provider="Another OS"), component(provider=PROVIDER),
        component(purl="pkg:pypi/openssl@1%3A3.0.1-astra2"),
        component(purl="pkg:deb/astra/openssl?arch=arm64"),
    ]}
    rows = list(analyze(doc, CATALOG))
    assert [row["status"] for row in rows] == [
        "match", "version", "invalid", "version", "match", "match", "missing", "missing",
    ]
    assert [row["index"] for row in rows if row["eligible"]] == [0]


def test_updates_only_the_selected_occurrence_and_preserves_structure():
    doc = {"bomFormat": "CycloneDX", "specVersion": "1.6",
           "dependencies": [{"ref": "root", "dependsOn": ["a", "b"]}],
           "components": [component("root", components=[
               component(**{"bom-ref": "a"}, provider=""),
               component(**{"bom-ref": "b"}),
           ])]}
    original = deepcopy(doc)
    apply_selection(doc, CATALOG, [1, 1])
    assert doc["components"][0]["components"][0]["properties"] == [
        {"name": PROPERTY, "value": PROVIDER},
    ]
    doc["components"][0]["components"][0]["properties"][0]["value"] = ""
    assert doc == original


def test_rejects_tampered_selection_without_partial_update():
    doc = {"components": [component(), component(version="bad")]}
    original = deepcopy(doc)
    with pytest.raises(ValueError):
        apply_selection(doc, CATALOG, [0, 1])
    assert doc == original
    with pytest.raises(ValueError):
        apply_selection({**doc, "signature": {}}, CATALOG, [0])


@pytest.mark.parametrize("spec", ["1.6", "1.7"])
def test_parses_both_checker_versions(spec):
    doc = {"bomFormat": "CycloneDX", "specVersion": spec, "components": []}
    assert parse_sbom(json.dumps(doc).encode("utf-8-sig")) == doc


def test_rejects_duplicate_keys():
    with pytest.raises(ValueError, match="JSON"):
        parse_sbom(b'{"components": [], "components": []}')


def test_catalog_counts_primary_names_and_uses_updates_only_for_those_names():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models import Base, CatalogPackage, CatalogSource
    from app.services.sbom_service import catalog_versions, load_catalog

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for repository, packages in {
            "frozen-main": [("openssl", "1"), ("libssl", "1")],
            "frozen-update-main": [("openssl", "2"), ("extra", "1")],
            "repository-base": [("base-only", "1")],
        }.items():
            source = CatalogSource(os_family="astra_linux", os_version="1.7.1",
                                   repository_name=repository, original_filename=repository,
                                   saved_path=repository)
            for name, version in packages:
                source.packages.append(CatalogPackage(
                    package_name=name, package_name_normalized=name, version_original=version,
                    version_normalized=version, architecture="amd64",
                ))
            db.add(source)
        db.commit()
        assert catalog_versions(db) == [{"version": "1.7.1", "series": "1.7", "count": 2}]
        assert dict(load_catalog(db, "1.7.1")) == {
            "openssl": [("2", "amd64", "frozen-update-main")],
            "libssl": [("1", "amd64", "frozen-main")],
        }


def test_apply_version_and_optional_astra_mark_preserves_references():
    doc = {"components": [component(
        version="old", purl="pkg:deb/astra/openssl@old?arch=amd64#src",
        **{"bom-ref": "openssl-old"},
    )], "dependencies": [{"ref": "openssl-old", "dependsOn": []}]}
    apply_selection(doc, CATALOG, [0], {0: "1:3.0.1-astra2"})
    updated = doc["components"][0]
    assert updated["version"] == "1:3.0.1-astra2"
    assert updated["purl"] == "pkg:deb/astra/openssl@1%3A3.0.1-astra2?arch=amd64#src"
    assert updated["properties"] == [{"name": PROPERTY, "value": PROVIDER}]
    assert updated["bom-ref"] == doc["dependencies"][0]["ref"] == "openssl-old"
    assert list(analyze(doc, CATALOG))[0]["status"] == "match"


def test_version_correction_requires_catalog_version_and_refuses_artifact_hashes():
    for item, version in [
        (component(version="old"), "unlisted"),
        (component(version="old", hashes=[{"alg": "SHA-256", "content": "a" * 64}]), "1:3.0.1-astra2"),
    ]:
        doc = {"components": [item]}
        original = deepcopy(doc)
        with pytest.raises(ValueError):
            apply_selection(doc, CATALOG, [0], {0: version})
        assert doc == original
