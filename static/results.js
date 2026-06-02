function initSearchModeTabs() {
    const tabs = document.querySelector("[data-search-mode-tabs]");
    if (!tabs) {
        return;
    }

    const advancedFlag = document.querySelector("[data-advanced-flag]");
    const advancedPanel = document.querySelector("[data-advanced-panel]");
    const advancedFields = document.querySelectorAll("[data-advanced-field]");
    const toggleButtons = tabs.querySelectorAll("[data-search-mode]");

    function applySearchMode(mode) {
        const normalized = mode === "advanced" ? "advanced" : "basic";
        toggleButtons.forEach((button) => {
            button.classList.toggle("active", button.dataset.searchMode === normalized);
        });
        if (advancedPanel) {
            advancedPanel.hidden = normalized !== "advanced";
        }
        if (advancedFlag) {
            advancedFlag.value = normalized === "advanced" ? "1" : "";
        }
        advancedFields.forEach((field) => {
            field.disabled = normalized !== "advanced";
        });
    }

    toggleButtons.forEach((button) => {
        button.addEventListener("click", () => applySearchMode(button.dataset.searchMode));
    });

    applySearchMode(tabs.dataset.defaultMode);
}

function initSourceCategoryFilter() {
    const sourceSelect = document.querySelector("[data-source-filter]");
    const categorySelect = document.querySelector("[data-category-filter]");
    if (!sourceSelect || !categorySelect) {
        return;
    }

    let sourceCategories = {};
    try {
        sourceCategories = JSON.parse(categorySelect.dataset.sourceCategories || "{}");
    } catch (error) {
        sourceCategories = {};
    }

    const fallbackCategories = Array.from(categorySelect.options)
        .map((option) => option.value)
        .filter(Boolean);
    const allCategories = Array.isArray(sourceCategories.__all__)
        ? sourceCategories.__all__
        : fallbackCategories;
    const allLabel = categorySelect.dataset.allLabel || "全部类别";

    function rebuildCategoryOptions() {
        const currentCategory = categorySelect.value;
        const selectedSource = sourceSelect.value;
        const categories = selectedSource && Array.isArray(sourceCategories[selectedSource])
            ? sourceCategories[selectedSource]
            : allCategories;

        categorySelect.innerHTML = "";
        categorySelect.appendChild(new Option(allLabel, ""));
        categories.forEach((category) => {
            categorySelect.appendChild(new Option(category, category));
        });
        categorySelect.value = categories.includes(currentCategory) ? currentCategory : "";
    }

    sourceSelect.addEventListener("change", rebuildCategoryOptions);
    rebuildCategoryOptions();
}

function escapeHtml(text) {
    return String(text || "—")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function highlightKeyword(text, keyword) {
    const safeText = escapeHtml(text || "—");
    if (!keyword) {
        return safeText;
    }
    const safeKeyword = escapeHtml(keyword);
    return safeText.split(safeKeyword).join(
        '<span class="segment-hit-word">' + safeKeyword + '</span>'
    );
}

function resetModalAudio() {
    const audio = document.getElementById("modalAudio");
    audio.pause();
    audio.removeAttribute("src");
    audio.onloadedmetadata = null;
    audio.ontimeupdate = null;
    audio.onerror = null;
    audio.load();
    return audio;
}

function openModal(item) {
    const audio = resetModalAudio();
    document.getElementById("modalTitle").innerText = item.title;
    document.getElementById("modalFileName").innerText = item.title;
    document.getElementById("modalSource").innerText = item.source || "未知";
    document.getElementById("modalCategory").innerText = item.category || "未分类";
    document.getElementById("modalYear").innerText = item.year || "未知";
    document.getElementById("modalDatasetName").innerText = item.datasetName || "—";
    document.getElementById("modalDialogueId").innerText = item.dialogueId || "—";
    document.getElementById("modalTimeRange").innerText = formatTimeRange(item.startTime, item.endTime);
    document.getElementById("modalSpeaker").innerText = item.speaker || "—";
    const labels = item.labels || {};
    document.getElementById("modalPrevLabel").innerText = labels.modal_prev || "前序话轮";
    document.getElementById("modalHitLabel").innerText = labels.modal_hit || "命中话轮";
    document.getElementById("modalNextLabel").innerText = labels.modal_next || "后续话轮";
    document.getElementById("modalPrevSegment").innerText = item.prevSegment || (item.isInterview ? "" : "—");
    document.getElementById("modalHitSegment").innerHTML = highlightKeyword(item.hitSegment, item.keyword);
    document.getElementById("modalNextSegment").innerText = item.nextSegment || (item.isInterview ? "" : "—");
    document.getElementById("modalCrawlSource").innerText = item.crawlSource || "—";
    document.getElementById("modalCrawlDate").innerText = item.crawlDate || "—";
    document.getElementById("modalLicenseNote").innerText = item.licenseNote || "";

    const sourceUrl = document.getElementById("modalSourceUrl");
    const sourceUrlMissing = document.getElementById("modalSourceUrlMissing");
    if (item.sourceUrl) {
        sourceUrl.href = item.sourceUrl;
        sourceUrl.style.display = "inline";
        sourceUrlMissing.style.display = "none";
    } else {
        sourceUrl.removeAttribute("href");
        sourceUrl.style.display = "none";
        sourceUrlMissing.style.display = "inline";
    }

    document.querySelectorAll(".interview-meta").forEach(function (element) {
        element.style.display = item.isInterview ? "block" : "none";
    });
    document.getElementById("modalLicenseNote").style.display = item.isInterview ? "block" : "none";

    const audioBox = document.getElementById("modalAudioBox");
    const audioUnavailable = document.getElementById("modalAudioUnavailable");
    if (item.audioUrl) {
        audio.style.display = "block";
        audioUnavailable.style.display = "none";
        audioBox.style.display = "block";
        audio.onloadedmetadata = function () {
            if (item.startTime !== null && item.startTime !== undefined) {
                const startTime = Number(item.startTime);
                if (!Number.isNaN(startTime)) {
                    audio.currentTime = startTime;
                }
            }
        };
        audio.ontimeupdate = function () {
            if (item.endTime === null || item.endTime === undefined || item.endTime === "") {
                return;
            }
            const endTime = Number(item.endTime);
            if (!Number.isNaN(endTime) && audio.currentTime >= endTime) {
                audio.pause();
            }
        };
        audio.onerror = function () {
            resetModalAudio();
            audio.style.display = "none";
            audioUnavailable.style.display = "block";
        };
        audio.src = item.audioUrl;
        audio.load();
    } else if (item.audioFile) {
        audio.style.display = "none";
        audioUnavailable.style.display = "block";
        audioBox.style.display = "block";
    } else {
        audio.style.display = "none";
        audioUnavailable.style.display = "none";
        audioBox.style.display = "none";
    }
    document.getElementById("contextModal").style.display = "flex";
}

function formatSeconds(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }
    const seconds = Number(value);
    if (Number.isNaN(seconds)) {
        return "—";
    }
    const minutes = Math.floor(seconds / 60);
    const rest = (seconds % 60).toFixed(2).padStart(5, "0");
    return minutes + ":" + rest;
}

function formatTimeRange(startTime, endTime) {
    if ((startTime === null || startTime === undefined || startTime === "") &&
        (endTime === null || endTime === undefined || endTime === "")) {
        return "—";
    }
    return formatSeconds(startTime) + " - " + formatSeconds(endTime);
}

function closeModal(event) {
    if (event.target.id === "contextModal") {
        resetModalAudio();
        document.getElementById("contextModal").style.display = "none";
    }
}

function closeModalDirect() {
    resetModalAudio();
    document.getElementById("contextModal").style.display = "none";
}

initSearchModeTabs();
initSourceCategoryFilter();
