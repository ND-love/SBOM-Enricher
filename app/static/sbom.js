(() => {
    const form = document.getElementById("sbom-export");
    if (!form) return;

    const rows = [...form.querySelectorAll("[data-sbom-status]")].map(element => ({
        element,
        status: element.dataset.sbomStatus,
        marked: element.dataset.sbomMarked === "1",
        text: element.textContent.toLowerCase(),
        checkbox: element.querySelector("[data-sbom-row]"),
        version: element.querySelector("[data-sbom-version]"),
    }));
    const candidates = rows.filter(row => row.status === "match").map(row => row.checkbox).filter(Boolean);
    const search = document.getElementById("sbom-search");
    const scope = document.getElementById("sbom-scope");
    const filters = [...document.querySelectorAll("[data-sbom-filter]")];
    const visibleCount = document.getElementById("sbom-visible");
    const empty = document.getElementById("sbom-empty");
    const selectAll = document.getElementById("sbom-all");
    const confirmation = document.getElementById("sbom-confirmed");
    const selection = document.getElementById("sbom-selection");
    const selectedCount = document.getElementById("sbom-count");
    const versions = document.getElementById("sbom-versions");
    const versionConfirmation = document.getElementById("sbom-version-confirmation");
    const versionsConfirmed = document.getElementById("sbom-versions-confirmed");
    const apply = document.getElementById("sbom-apply");
    let status = "";

    function filterRows() {
        const query = search.value.trim().toLowerCase();
        let visible = 0;
        rows.forEach(row => {
            const matchesScope = {
                "": true,
                related: row.marked || row.status !== "missing",
                marked: row.marked,
                eligible: Boolean(row.checkbox),
                unrelated: !row.marked && row.status === "missing",
            }[scope.value];
            const show = matchesScope && (!status || row.status === status) && row.text.includes(query);
            row.element.hidden = !show;
            visible += Number(show);
        });
        visibleCount.textContent = `${visible} из ${rows.length}`;
        empty.hidden = visible > 0;
    }

    function updateSelection() {
        const replacements = {};
        const selected = [];
        rows.forEach(({checkbox, version}) => {
            if (version) {
                if (version.value) replacements[version.dataset.sbomVersion] = version.value;
                if (checkbox) {
                    checkbox.disabled = !version.value;
                    if (checkbox.disabled) checkbox.checked = false;
                }
            }
            if (checkbox?.checked) selected.push(Number(checkbox.dataset.sbomRow));
        });
        const versionCount = Object.keys(replacements).length;
        const exactSelected = candidates.filter(box => box.checked).length;
        selection.value = JSON.stringify(selected);
        versions.value = JSON.stringify(replacements);
        selectedCount.textContent = `Отметок: ${selected.length} · Версий: ${versionCount}`;
        selectAll.disabled = candidates.length === 0;
        selectAll.checked = candidates.length > 0 && exactSelected === candidates.length;
        selectAll.indeterminate = exactSelected > 0 && exactSelected < candidates.length;
        confirmation.required = selected.length > 0;
        versionConfirmation.hidden = !versionCount;
        versionsConfirmed.required = versionCount > 0;
        if (!versionCount) versionsConfirmed.checked = false;
        apply.disabled = (!selected.length && !versionCount)
            || (selected.length > 0 && !confirmation.checked)
            || (versionCount > 0 && !versionsConfirmed.checked);
    }

    filters.forEach(button => button.addEventListener("click", () => {
        status = button.dataset.sbomFilter;
        filters.forEach(filter => filter.setAttribute("aria-pressed", String(filter === button)));
        filterRows();
    }));
    search.addEventListener("input", filterRows);
    scope.addEventListener("change", filterRows);
    selectAll.addEventListener("change", () => {
        candidates.forEach(box => { box.checked = selectAll.checked; });
    });
    form.addEventListener("change", event => {
        if (event.target.matches("[data-sbom-version]")) versionsConfirmed.checked = false;
        updateSelection();
    });
    updateSelection();
    filterRows();
})();
