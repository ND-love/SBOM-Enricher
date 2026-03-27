from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.catalog_utils import make_target_label, prettify_os_family
from app.config import ALIASES_PATH, REPORTS_DIR, TEMPLATES_DIR, UPLOADS_DIR
from app.db import SessionLocal
from app.parsers.input_docx_parser import InputDocxValidationError, parse_input_docx
from app.reporting.excel_report_builder import build_multi_target_excel_report
from app.repositories.catalog_repository import CatalogRepository
from app.services.catalog_compare_service import CatalogCompareService
from app.services.catalog_lookup_service import CatalogLookupService

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _load_targets() -> list[dict[str, object]]:
    db = SessionLocal()
    try:
        repo = CatalogRepository()
        targets = repo.list_targets(db)
    finally:
        db.close()

    prepared: list[dict[str, object]] = []
    for item in targets:
        os_family = str(item["os_family"])
        os_version = str(item["os_version"])
        prepared.append(
            {
                **item,
                "label": make_target_label(os_family, os_version),
                "family_label": prettify_os_family(os_family),
                "target_key": f"{os_family}:{os_version}",
            }
        )
    return sorted(prepared, key=lambda x: (str(x["os_family"]), str(x["os_version"])))


def _target_from_key(targets: list[dict[str, object]], target_key: str | None) -> dict[str, object] | None:
    if not target_key:
        return targets[0] if targets else None
    for target in targets:
        if target["target_key"] == target_key:
            return target
    return None


def _targets_from_keys(targets: list[dict[str, object]], target_keys: list[str] | None) -> list[dict[str, object]]:
    if not target_keys:
        return []

    seen: set[str] = set()
    prepared: list[dict[str, object]] = []

    for key in target_keys:
        if key in seen:
            continue
        seen.add(key)

        target = _target_from_key(targets, key)
        if target is not None:
            prepared.append(target)

    return prepared


def _empty_context(request: Request) -> dict[str, object]:
    targets = _load_targets()
    default_target = targets[0] if targets else None
    default_check_targets = [default_target["target_key"]] if default_target else []

    return {
        "request": request,
        "error": None,
        "targets": targets,
        "selected_check_target_keys": default_check_targets,
        "selected_compare_left_key": default_target["target_key"] if default_target else None,
        "selected_compare_right_key": targets[1]["target_key"] if len(targets) > 1 else (default_target["target_key"] if default_target else None),
        "selected_family_target_key": default_target["target_key"] if default_target else None,
        "check_summary": None,
        "check_results": [],
        "report_download_url": None,
        "compare_summary": None,
        "compare_results": [],
        "compare_left_label": None,
        "compare_right_label": None,
        "family_summary": None,
        "family_versions": [],
        "family_rows": [],
        "family_label": None,
    }


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", _empty_context(request))


@router.post("/check", response_class=HTMLResponse)
async def check_catalog(
    request: Request,
    input_file: UploadFile = File(...),
    target_keys: list[str] = Form([]),
):
    context = _empty_context(request)
    context["selected_check_target_keys"] = target_keys

    targets = context["targets"]
    selected_targets = _targets_from_keys(targets, target_keys)

    if not selected_targets:
        context["error"] = "Нужно выбрать хотя бы одну целевую ОС."
        return templates.TemplateResponse(request, "index.html", context, status_code=400)

    if len(selected_targets) > 5:
        context["error"] = "Можно выбрать не более 5 систем."
        return templates.TemplateResponse(request, "index.html", context, status_code=400)

    if len(selected_targets) != len({key for key in target_keys}):
        context["error"] = "Одна или несколько выбранных ОС не найдены в каталоге."
        return templates.TemplateResponse(request, "index.html", context, status_code=400)

    if not input_file.filename:
        context["error"] = "Файл не был выбран."
        return templates.TemplateResponse(request, "index.html", context, status_code=400)

    suffix = Path(input_file.filename).suffix.lower()
    if suffix != ".docx":
        context["error"] = "Поддерживается только формат .docx."
        return templates.TemplateResponse(request, "index.html", context, status_code=400)

    unique_prefix = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    saved_input_path = UPLOADS_DIR / f"{unique_prefix}_{Path(input_file.filename).name}"
    saved_input_path.write_bytes(await input_file.read())

    try:
        input_rows = parse_input_docx(saved_input_path)
    except (FileNotFoundError, ValueError, InputDocxValidationError) as exc:
        context["error"] = str(exc)
        return templates.TemplateResponse(request, "index.html", context, status_code=400)

    db = SessionLocal()
    try:
        lookup_service = CatalogLookupService(repository=CatalogRepository(), aliases_path=ALIASES_PATH)

        report_rows: list[dict[str, object]] = []
        ui_rows: list[dict[str, object]] = []

        per_target_counters: dict[str, dict[str, int]] = {
            str(target["target_key"]): {
                "exact": 0,
                "different_version": 0,
                "absent": 0,
                "unresolved": 0,
            }
            for target in selected_targets
        }

        for input_row in input_rows:
            row_target_cells: list[dict[str, object]] = []
            row_target_results: list[dict[str, object]] = []

            for target in selected_targets:
                result = lookup_service.lookup_component(
                    db,
                    os_family=str(target["os_family"]),
                    os_version=str(target["os_version"]),
                    component_name=str(input_row["component_original"]),
                    requested_version=str(input_row["version_original"]),
                )

                status = str(result["status"])
                per_target_counters[str(target["target_key"])][status] += 1

                matches = result.get("matches", []) or []
                first_match = matches[0] if matches else None
                found_versions = result.get("found_versions", []) or []

                row_target_results.append(
                    {
                        "target_label": str(target["label"]),
                        "lookup_result": result,
                    }
                )

                row_target_cells.append(
                    {
                        "target_label": str(target["label"]),
                        "status": status,
                        "status_label": _status_label(status),
                        "display_value": ", ".join(str(x) for x in found_versions) if found_versions else "—",
                        "message": str(result.get("message") or ""),
                        "resolved_component_name": str(result.get("resolved_component_name") or ""),
                        "was_aliased": bool(result.get("was_aliased")),
                        "repository_name": first_match.get("repository_name") if first_match else "",
                        "filename": first_match.get("filename") if first_match else "",
                    }
                )

            report_rows.append(
                {
                    "input_row": input_row,
                    "target_results": row_target_results,
                }
            )

            ui_rows.append(
                {
                    "component": str(input_row["component_original"]),
                    "requested_version": str(input_row["version_original"]),
                    "target_cells": row_target_cells,
                }
            )

        report_filename = f"report_{unique_prefix}.xlsx"
        report_path = REPORTS_DIR / report_filename

        build_multi_target_excel_report(
            report_path,
            target_labels=[str(target["label"]) for target in selected_targets],
            rows=report_rows,
        )

        context["check_results"] = ui_rows
        context["check_summary"] = {
            "checked_rows": len(ui_rows),
            "selected_target_count": len(selected_targets),
            "targets": [
                {
                    "label": str(target["label"]),
                    "exact": per_target_counters[str(target["target_key"])]["exact"],
                    "different_version": per_target_counters[str(target["target_key"])]["different_version"],
                    "absent": per_target_counters[str(target["target_key"])]["absent"],
                    "unresolved": per_target_counters[str(target["target_key"])]["unresolved"],
                }
                for target in selected_targets
            ],
        }
        context["report_download_url"] = f"/download/{report_filename}"

        return templates.TemplateResponse(request, "index.html", context)
    finally:
        db.close()


@router.post("/compare", response_class=HTMLResponse)
def compare_targets(
    request: Request,
    left_target_key: str = Form(...),
    right_target_key: str = Form(...),
):
    context = _empty_context(request)
    context["selected_compare_left_key"] = left_target_key
    context["selected_compare_right_key"] = right_target_key

    left_target = _target_from_key(context["targets"], left_target_key)
    right_target = _target_from_key(context["targets"], right_target_key)

    if left_target is None or right_target is None:
        context["error"] = "Одна из выбранных ОС не найдена в каталоге."
        return templates.TemplateResponse(request, "index.html", context, status_code=400)

    db = SessionLocal()
    try:
        service = CatalogCompareService(repository=CatalogRepository())
        rows = service.compare_targets(
            db,
            left_family=str(left_target["os_family"]),
            left_version=str(left_target["os_version"]),
            right_family=str(right_target["os_family"]),
            right_version=str(right_target["os_version"]),
        )
    finally:
        db.close()

    counters = {"same_version": 0, "different_version": 0, "only_left": 0, "only_right": 0}
    for row in rows:
        status = str(row["status"])
        counters[status] = counters.get(status, 0) + 1

    context["compare_results"] = rows
    context["compare_summary"] = {"total": len(rows), **counters}
    context["compare_left_label"] = left_target["label"]
    context["compare_right_label"] = right_target["label"]
    return templates.TemplateResponse(request, "index.html", context)


@router.post("/family-view", response_class=HTMLResponse)
def family_view(
    request: Request,
    target_key: str = Form(...),
):
    context = _empty_context(request)
    context["selected_family_target_key"] = target_key
    target = _target_from_key(context["targets"], target_key)

    if target is None:
        context["error"] = "Выбранная ОС не найдена в каталоге."
        return templates.TemplateResponse(request, "index.html", context, status_code=400)

    db = SessionLocal()
    try:
        service = CatalogCompareService(repository=CatalogRepository())
        matrix = service.build_family_matrix(
            db,
            os_family=str(target["os_family"]),
            anchor_version=str(target["os_version"]),
        )
    finally:
        db.close()

    context["family_versions"] = matrix["versions"]
    context["family_rows"] = matrix["rows"]
    context["family_summary"] = {"total": len(matrix["rows"]), "series": matrix["series"]}
    context["family_label"] = prettify_os_family(str(target["os_family"]))
    return templates.TemplateResponse(request, "index.html", context)


@router.get("/download/{report_name}")
def download_report(report_name: str):
    safe_name = Path(report_name).name
    report_path = REPORTS_DIR / safe_name
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Отчет не найден")
    return FileResponse(
        path=report_path,
        filename=safe_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _status_label(status: str) -> str:
    mapping = {
        "exact": "Точное совпадение",
        "different_version": "Другая версия",
        "absent": "Не найден",
        "unresolved": "Неопределенно",
        "same_version": "Одинаково",
        "only_left": "Только слева",
        "only_right": "Только справа",
    }
    return mapping.get(status, status)