import json
import re
from collections import Counter
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response

from app.config import ASTRA_RAW_DIR, UPLOADS_DIR
from app.db import SessionLocal
from app.routes.ui import page_context, templates
from app.services.sbom_service import MAX_SIZE, analyze, apply_selection, catalog_versions, load_catalog, parse_sbom

router = APIRouter(prefix="/sbom")
STORAGE = UPLOADS_DIR / "sbom"
CATALOG_DOCS = {
    "1.6": "https://wiki.astralinux.ru/pages/viewpage.action?pageId=3276905",
    "1.7": "https://dl.astralinux.ru/astra/frozen/1.7_x86-64/",
    "1.8": "https://dl.astralinux.ru/astra/frozen/1.8_x86-64/",
}


def official_indexes(version):
    manifest = ASTRA_RAW_DIR / "SOURCES.tsv"
    if not version or not manifest.is_file():
        return []
    records = (line.split() for line in manifest.read_text().splitlines()[1:])
    return [(name.removesuffix(".txt"), url) for name, _, url in records
            if name.startswith(f"{version}-frozen-")]


def page(request, version="", **context):
    with SessionLocal() as db:
        releases = catalog_versions(db)
    counts = Counter(row["status"] for row in context.get("rows", []))
    sbom = {
        "releases": releases,
        "version": version or (releases[0]["version"] if releases else ""),
        "indexes": official_indexes(version),
        "catalog_link": CATALOG_DOCS.get(".".join(version.split(".")[:2])),
        "counts": counts,
        **context,
    }
    return templates.TemplateResponse(
        request, "index.html", {**page_context(request), "sbom": sbom},
        status_code=400 if "error" in context else 200,
    )


def original_path(upload_id):
    if not re.fullmatch(r"[0-9a-f]{32}", upload_id):
        raise HTTPException(404)
    path = STORAGE / f"{upload_id}.json"
    if not path.is_file():
        raise HTTPException(404)
    return path


def revision_path(upload_id, edit_id):
    original_path(upload_id)
    if not re.fullmatch(r"[0-9a-f]{32}", edit_id):
        raise HTTPException(404)
    path = STORAGE / f"{upload_id}-{edit_id}.json"
    if not path.is_file():
        raise HTTPException(404)
    return path


@router.get("")
def sbom_page(request: Request):
    return page(request)


@router.post("")
def check_sbom(
    request: Request, release: str = Form(), file: UploadFile | None = File(None),
    upload_id: str = Form(""), edit_id: str = Form(""),
):
    try:
        if file and file.filename:
            raw = file.file.read(MAX_SIZE + 1)
        elif upload_id:
            raw = (revision_path(upload_id, edit_id) if edit_id else original_path(upload_id)).read_bytes()
        else:
            raise ValueError("Выберите файл SBOM")
        doc = parse_sbom(raw, max_size=None if edit_id and not (file and file.filename) else MAX_SIZE)
        with SessionLocal() as db:
            rows = list(analyze(doc, load_catalog(db, release)))
    except (ValueError, RecursionError) as exc:
        return page(request, release, error=str(exc), upload_id=upload_id, edit_id=edit_id)

    if file and file.filename:
        upload_id = uuid4().hex
        edit_id = ""
        STORAGE.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (STORAGE / f"{upload_id}.json").open("xb") as original:
            original.write(raw)
    return page(request, release, rows=rows, upload_id=upload_id, edit_id=edit_id)


@router.get("/{upload_id}/original")
def original_sbom(upload_id: str):
    return FileResponse(original_path(upload_id), media_type="application/json",
                        filename="sbom-original.json")


@router.post("/{upload_id}/export")
def export_sbom(upload_id: str, release: str = Form(), selection: str = Form("[]"),
                confirmed: bool = Form(False)):
    path = original_path(upload_id)
    try:
        indices = json.loads(selection)
        if not isinstance(indices, list) or (indices and not confirmed):
            raise ValueError("Подтвердите происхождение выбранных компонентов")
        if not indices:
            return original_sbom(upload_id)
        doc = parse_sbom(path.read_bytes())
        with SessionLocal() as db:
            apply_selection(doc, load_catalog(db, release), indices)
        result = json.dumps(doc, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
    except (ValueError, RecursionError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return Response(result, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="sbom-astra.json"'})


@router.post("/{upload_id}/apply")
def apply_sbom(
    request: Request, upload_id: str, release: str = Form(),
    edit_id: str = Form(""), selection: str = Form("[]"), versions: str = Form("{}"),
    confirmed: bool = Form(False), versions_confirmed: bool = Form(False),
):
    path = revision_path(upload_id, edit_id) if edit_id else original_path(upload_id)
    with SessionLocal() as db:
        try:
            doc = parse_sbom(path.read_bytes(), max_size=None if edit_id else MAX_SIZE)
            catalog = load_catalog(db, release)
            rows = list(analyze(doc, catalog))
        except (ValueError, RecursionError) as exc:
            return page(request, release, error=str(exc), upload_id=upload_id, edit_id=edit_id)
    try:
        indices = json.loads(selection)
        requested = json.loads(versions)
        if not isinstance(indices, list) or not isinstance(requested, dict):
            raise ValueError("Некорректный выбор изменений")
        replacements = {int(key): value for key, value in requested.items()}
        if not (indices or replacements):
            raise ValueError("Отметьте пакеты или выберите версии для замены")
        if indices and not confirmed:
            raise ValueError("Подтвердите происхождение пакетов для отметки Astra")
        if replacements and not versions_confirmed:
            raise ValueError("Подтвердите фактически используемые версии и относящиеся к ним данные")
        apply_selection(doc, catalog, indices, replacements)
        result = json.dumps(doc, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
    except (ValueError, RecursionError) as exc:
        return page(request, release, rows=rows, error=str(exc), upload_id=upload_id, edit_id=edit_id)

    new_edit_id = uuid4().hex
    with (STORAGE / f"{upload_id}-{new_edit_id}.json").open("x", encoding="utf-8") as output:
        output.write(result)
    return page(
        request, release, rows=list(analyze(doc, catalog)), upload_id=upload_id,
        edit_id=new_edit_id, applied={"marks": set(indices), "versions": set(replacements)},
    )


@router.get("/{upload_id}/revision/{edit_id}")
def download_revision(upload_id: str, edit_id: str):
    return FileResponse(revision_path(upload_id, edit_id), media_type="application/json",
                        filename="sbom-astra.json")
