from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


GREEN_FILL = PatternFill(fill_type="solid", fgColor="C6EFCE")
YELLOW_FILL = PatternFill(fill_type="solid", fgColor="FFF2CC")
RED_FILL = PatternFill(fill_type="solid", fgColor="F4CCCC")
BLUE_FILL = PatternFill(fill_type="solid", fgColor="D9EAF7")
HEADER_FILL = PatternFill(fill_type="solid", fgColor="D9D9D9")

THIN_BORDER = Border(
    left=Side(style="thin", color="999999"),
    right=Side(style="thin", color="999999"),
    top=Side(style="thin", color="999999"),
    bottom=Side(style="thin", color="999999"),
)


def build_multi_target_excel_report(
    output_path: str | Path,
    *,
    target_labels: list[str],
    rows: list[dict[str, object]],
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    comparison_ws = workbook.active
    comparison_ws.title = "comparison"
    summary_ws = workbook.create_sheet("summary")

    _build_comparison_sheet(comparison_ws, target_labels=target_labels, rows=rows)
    _build_summary_sheet(summary_ws, rows=rows, target_labels=target_labels)

    workbook.save(output_path)


def build_single_target_excel_report(
    output_path: str | Path,
    *,
    target_label: str,
    rows: list[dict[str, object]],
) -> None:
    build_multi_target_excel_report(
        output_path,
        target_labels=[target_label],
        rows=[
            {
                "input_row": item["input_row"],
                "target_results": [
                    {
                        "target_label": target_label,
                        "lookup_result": item["lookup_result"],
                    }
                ],
            }
            for item in rows
        ],
    )


def build_astra_excel_report(
    output_path: str | Path,
    *,
    astra_version: str,
    rows: list[dict[str, object]],
) -> None:
    build_single_target_excel_report(
        output_path,
        target_label=f"Astra Linux {astra_version}",
        rows=rows,
    )


def _build_comparison_sheet(ws, *, target_labels: list[str], rows: list[dict[str, object]]) -> None:
    headers = ["component", "version", *target_labels]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER

    for excel_row_index, item in enumerate(rows, start=2):
        input_row = item["input_row"]
        target_results = item.get("target_results", []) or []

        result_map = {
            str(target_item["target_label"]): target_item["lookup_result"]
            for target_item in target_results
        }

        component_original = str(input_row["component_original"])
        version_original = str(input_row["version_original"])
        is_version_missing = bool(input_row["is_version_missing"])

        ws.cell(row=excel_row_index, column=1, value=component_original)
        ws.cell(row=excel_row_index, column=2, value=version_original)

        for target_index, target_label in enumerate(target_labels, start=3):
            result = result_map.get(target_label, {"status": "unresolved", "found_versions": []})
            status = str(result.get("status", "unresolved"))
            found_versions = result.get("found_versions", []) or []

            value = ", ".join(str(x) for x in found_versions) if found_versions else "—"
            target_cell = ws.cell(row=excel_row_index, column=target_index, value=value)
            target_cell.fill = _fill_for_status(status)

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=excel_row_index, column=col_idx)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = THIN_BORDER

        if is_version_missing:
            for col_idx in range(1, len(headers) + 1):
                ws.cell(row=excel_row_index, column=col_idx).fill = BLUE_FILL

    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions
    _autofit_columns(ws)


def _build_summary_sheet(ws, *, rows: list[dict[str, object]], target_labels: list[str]) -> None:
    ws.append(["checked_rows", len(rows)])
    ws.append(["selected_targets", len(target_labels)])
    ws.append([])
    ws.append(["target_os", "exact", "different_version", "absent", "unresolved"])

    for cell in ws[4]:
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER

    for target_label in target_labels:
        counters = {
            "exact": 0,
            "different_version": 0,
            "absent": 0,
            "unresolved": 0,
        }

        for item in rows:
            target_results = item.get("target_results", []) or []
            for target_item in target_results:
                if str(target_item["target_label"]) != target_label:
                    continue
                status = str(target_item["lookup_result"].get("status", "unresolved"))
                counters[status] = counters.get(status, 0) + 1
                break

        ws.append(
            [
                target_label,
                counters["exact"],
                counters["different_version"],
                counters["absent"],
                counters["unresolved"],
            ]
        )

    ws.append([])
    ws.append(["legend", "meaning"])
    ws.append(["green", "точная версия найдена"])
    ws.append(["yellow", "компонент найден, но версия другая"])
    ws.append(["red", "компонент не найден"])
    ws.append(["blue", "неопределенный случай / пустая версия / требуется ручная проверка"])

    for row in ws.iter_rows():
        for cell in row:
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    _autofit_columns(ws)


def _fill_for_status(status: str) -> PatternFill:
    if status == "exact":
        return GREEN_FILL
    if status == "different_version":
        return YELLOW_FILL
    if status == "absent":
        return RED_FILL
    return BLUE_FILL


def _autofit_columns(ws) -> None:
    for column_cells in ws.columns:
        max_length = 0
        column_index = column_cells[0].column
        for cell in column_cells:
            value = "" if cell.value is None else str(cell.value)
            max_length = max(max_length, len(value))
        ws.column_dimensions[get_column_letter(column_index)].width = min(max(max_length + 2, 14), 36)