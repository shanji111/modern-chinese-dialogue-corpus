(function () {
    /* ========== State / DOM Cache ========== */
    const form = document.querySelector("[data-resonance-form]");
    const list = document.querySelector("[data-results]");
    const resultsPanel = document.querySelector("[data-results-panel]");
    const pagination = document.querySelector("[data-pagination]");
    const loading = document.querySelector("[data-loading]");
    const errorBox = document.querySelector("[data-error]");
    const summary = document.querySelector("[data-summary]");
    const range = document.querySelector("[data-result-range]");
    const searchButton = document.querySelector("[data-search-button]");
    const presetInput = document.querySelector("[data-preset-input]");
    const statusBar = document.querySelector("[data-status-bar]");
    const requestCache = new Map();

    let busy = false;
    let slowTimer = null;
    let currentMode = "sample";
    let currentPage = 1;
    let cursorHistory = [""];
    let nextCursor = "";

    if (!form || !list || !pagination) {
        return;
    }

    /* ========== Utility Functions ========== */
    function setLoading(active, message) {
        if (loading) {
            loading.hidden = !active;
            loading.textContent = message || (currentMode === "sample" ? "正在加载对话句法样例……" : "正在检索相邻话轮，请稍候……");
        }
        if (searchButton) {
            searchButton.disabled = active;
        }
        document.querySelectorAll("[data-page-prev], [data-page-next], [data-preset]").forEach((button) => {
            button.disabled = active;
        });
    }

    function setError(message) {
        if (!errorBox) {
            return;
        }
        errorBox.hidden = !message;
        errorBox.textContent = message || "";
    }

    function getKeyword() {
        return (new FormData(form).get("q") || "").trim();
    }

    /* ========== API Requests ========== */
    function buildUrl({cursor = "", sample = false} = {}) {
        const url = new URL(form.action, window.location.origin);
        const data = new FormData(form);
        for (const [key, value] of data.entries()) {
            if (value !== "") {
                url.searchParams.set(key, value);
            }
        }
        if (sample) {
            url.searchParams.set("sample", "1");
        }
        if (cursor) {
            url.searchParams.set("cursor", cursor);
        }
        url.searchParams.set("start", "1");
        return url;
    }

    async function fetchCached(url) {
        const key = url.toString();
        if (!requestCache.has(key)) {
            requestCache.set(key, fetch(key, {headers: {"X-Requested-With": "fetch"}}).then((response) => {
                if (!response.ok) {
                    throw new Error("request failed");
                }
                return response.json();
            }));
        }
        return requestCache.get(key);
    }

    /* ========== Loading / Status UI ========== */
    function startSlowNotice() {
        clearTimeout(slowTimer);
        slowTimer = setTimeout(() => {
            if (loading && !loading.hidden) {
                loading.textContent = "查询较慢，建议输入更多关键词或缩小来源/类别。";
            }
        }, 10000);
    }

    function stopSlowNotice() {
        clearTimeout(slowTimer);
        slowTimer = null;
    }

    function updateStatus(data) {
        const count = data.count || 0;
        if (currentMode === "sample") {
            if (summary) {
                summary.textContent = `样例模式：第 ${currentPage} 页，已显示 ${count} 条对话句法样例`;
            }
            if (range) {
                range.textContent = "样例模式";
            }
            return;
        }
        if (summary) {
            summary.textContent = `已完成本次对话句法检索，当前第 ${currentPage} 页`;
        }
        if (range) {
            range.textContent = count ? `本页 ${count} 条` : "暂无候选";
        }
    }

    /* ========== Pagination ========== */
    function renderPagination(hasNext) {
        pagination.innerHTML = `
            <button type="button" class="page-nav-button" data-page-prev ${currentPage <= 1 ? "disabled" : ""}>‹ 上一页</button>
            <span class="current-page">第 ${currentPage} 页</span>
            <button type="button" class="page-nav-button" data-page-next ${hasNext ? "" : "disabled"}>下一页 ›</button>
        `;
    }

    function scrollToResults() {
        if (resultsPanel) {
            resultsPanel.scrollTop = 0;
        }
        if (statusBar) {
            statusBar.scrollIntoView({behavior: "smooth", block: "start"});
        }
    }

    /* ========== Resonance Search ========== */
    async function runPage({page = 1, cursor = "", sample = currentMode === "sample"} = {}) {
        if (busy) {
            return;
        }
        const keyword = getKeyword();
        if (!sample && keyword && keyword.length < 2) {
            setError("关键词过短，可能产生大量结果。请尝试输入两个字以上的表达，如‘我觉得’‘台湾问题’。");
            return;
        }
        if (!sample && !keyword) {
            sample = true;
        }

        busy = true;
        currentMode = sample ? "sample" : "search";
        currentPage = page;
        setError("");
        setLoading(true, sample ? "正在加载对话句法样例……" : "正在检索相邻话轮，请稍候……");
        startSlowNotice();

        try {
            const data = await fetchCached(buildUrl({cursor, sample}));
            if (data.error_message) {
                setError(data.error_message);
            }
            list.innerHTML = data.html || "";
            if (!data.count) {
                list.innerHTML = sample
                    ? '<div class="no-result">样例加载失败，请输入关键词后检索。</div>'
                    : '<div class="no-result">当前模式和筛选条件下暂无对话句法候选。</div>';
            }
            nextCursor = data.next_cursor || "";
            cursorHistory[currentPage] = cursor || "";
            if (data.has_next && nextCursor) {
                cursorHistory[currentPage + 1] = nextCursor;
            }
            updateStatus(data);
            renderPagination(Boolean(data.has_next && nextCursor));
            scrollToResults();
        } catch (error) {
            setError(sample ? "样例加载失败，请输入关键词后检索。" : "加载失败，请稍后重试。");
            renderPagination(false);
        } finally {
            stopSlowNotice();
            busy = false;
            setLoading(false);
        }
    }

    function resetPaging() {
        cursorHistory = [""];
        nextCursor = "";
        currentPage = 1;
        requestCache.clear();
    }

    /* ========== Context Loading ========== */
    async function loadContext(details) {
        if (!details || details.dataset.loaded === "1") {
            return;
        }
        const target = details.querySelector("[data-context-content]");
        const url = details.dataset.contextUrl;
        if (!target || !url) {
            return;
        }
        details.dataset.loaded = "1";
        target.textContent = "正在加载原文上下文...";
        try {
            const data = await fetchCached(new URL(url, window.location.origin));
            target.textContent = data.content || data.error || "未找到原文上下文。";
            if (data.truncated) {
                target.textContent += "\n\n（原文较长，已截取前段用于预览。）";
            }
        } catch (error) {
            details.dataset.loaded = "";
            target.textContent = "原文上下文加载失败，请稍后重试。";
        }
    }

    /* ========== Diagraph Helpers / API URLs ========== */
    function escapeHtml(value) {
        return (value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function buildDiagraphUrl(pairId, windowMode) {
        const url = new URL(`/api/diagraph/${pairId}`, window.location.origin);
        url.searchParams.set("window", windowMode || "pair");
        return url;
    }

    function buildDiagraphExportUrl(pairId, windowMode) {
        const url = new URL("/api/diagraph/export_csv", window.location.origin);
        url.searchParams.set("pair_id", pairId);
        url.searchParams.set("window", windowMode || "pair");
        return url.toString();
    }

    function setDiagraphLoading(panel, active, message) {
        const loadingBox = panel.querySelector("[data-diagraph-loading]");
        if (!loadingBox) {
            return;
        }
        loadingBox.hidden = !active;
        loadingBox.textContent = message || "正在生成跨句图谱...";
    }

    function setDiagraphError(panel, message) {
        const errorBox = panel.querySelector("[data-diagraph-error]");
        if (!errorBox) {
            return;
        }
        errorBox.hidden = !message;
        errorBox.textContent = message || "";
    }

    /* ========== Diagraph Rendering ========== */
    function renderDiagraphGrid(data) {
        const headers = data.columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("");
        const rows = (data.grid || []).map((row) => {
            const cells = data.columns.map((column) => {
                const value = (row.cells || {})[column] || "";
                return `<td class="${value ? "filled" : ""}">${escapeHtml(value)}</td>`;
            }).join("");
            return `
                <tr>
                    <th class="diagraph-row-no">${escapeHtml(String(row.row_no || ""))}</th>
                    <th class="diagraph-row-speaker">${escapeHtml(row.speaker || "")}</th>
                    ${cells}
                </tr>
            `;
        }).join("");
        return `
            <section class="diagraph-block">
                <div class="diagraph-block-title">跨句图谱表</div>
                <div class="diagraph-table-scroll">
                    <table class="diagraph-grid-table">
                        <thead>
                            <tr>
                                <th class="diagraph-row-no">行号</th>
                                <th class="diagraph-row-speaker">说话人</th>
                                ${headers}
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </section>
        `;
    }

    function renderAffordances(data) {
        const items = data.affordances || [];
        const rows = items.length ? items.map((item) => `
            <tr>
                <td>${escapeHtml(item.column || "")}</td>
                <td>${escapeHtml(item.mapping || "")}</td>
                <td>${escapeHtml(item.relation || "")}</td>
                <td>${escapeHtml(item.description || "")}</td>
            </tr>
        `).join("") : `
            <tr>
                <td colspan="4">当前窗口未识别出可归纳的结构关系，可结合上下文人工校订。</td>
            </tr>
        `;
        return `
            <section class="diagraph-block">
                <div class="diagraph-block-title">结构可供性表</div>
                <div class="diagraph-table-scroll">
                    <table class="diagraph-affordance-table">
                        <thead>
                            <tr>
                                <th>纵栏</th>
                                <th>映射</th>
                                <th>关系</th>
                                <th>描述</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </section>
        `;
    }

    function renderDiagraphPayload(data) {
        return `
            <div class="diagraph-notice">${escapeHtml(data.notice || "")}</div>
            ${renderDiagraphGrid(data)}
            ${renderAffordances(data)}
        `;
    }

    /* ========== Diagraph Export / Copy ========== */
    function serializeDiagraphText(data) {
        const lines = [];
        lines.push("跨句图谱");
        lines.push(data.notice || "");
        lines.push("");
        lines.push(["行号", "说话人", ...(data.columns || [])].join("\t"));
        (data.grid || []).forEach((row) => {
            lines.push([
                row.row_no || "",
                row.speaker || "",
                ...(data.columns || []).map((column) => ((row.cells || {})[column] || "")),
            ].join("\t"));
        });
        lines.push("");
        lines.push("结构可供性表");
        lines.push(["纵栏", "映射", "关系", "描述"].join("\t"));
        (data.affordances || []).forEach((item) => {
            lines.push([item.column || "", item.mapping || "", item.relation || "", item.description || ""].join("\t"));
        });
        return lines.join("\n");
    }

    /* ========== Diagraph Loading ========== */
    async function loadDiagraph(panel, pairId, windowMode) {
        if (!panel || !pairId) {
            return;
        }
        const content = panel.querySelector("[data-diagraph-content]");
        const exportLink = panel.querySelector("[data-diagraph-export]");
        const normalizedWindow = windowMode || "pair";
        panel.dataset.window = normalizedWindow;
        if (exportLink) {
            exportLink.href = buildDiagraphExportUrl(pairId, normalizedWindow);
        }
        setDiagraphError(panel, "");
        setDiagraphLoading(panel, true, "正在生成跨句图谱...");
        try {
            const data = await fetchCached(buildDiagraphUrl(pairId, normalizedWindow));
            panel.diagraphData = data;
            if (content) {
                content.innerHTML = renderDiagraphPayload(data);
            }
        } catch (error) {
            panel.diagraphData = null;
            if (content) {
                content.innerHTML = "";
            }
            setDiagraphError(panel, "跨句图谱生成失败，请稍后重试。");
        } finally {
            setDiagraphLoading(panel, false);
        }
    }

    /* ========== Event Binding ========== */
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        resetPaging();
        runPage({sample: false});
    });

    document.addEventListener("click", (event) => {
        const presetButton = event.target.closest("[data-preset]");
        if (presetButton && presetInput) {
            document.querySelectorAll("[data-preset]").forEach((button) => button.classList.remove("active"));
            presetButton.classList.add("active");
            presetInput.value = presetButton.dataset.preset || "resonance";
            resetPaging();
            runPage({sample: getKeyword().length < 2});
            return;
        }

        if (event.target.closest("[data-page-next]")) {
            if (nextCursor) {
                runPage({page: currentPage + 1, cursor: nextCursor, sample: currentMode === "sample"});
            }
            return;
        }

        if (event.target.closest("[data-page-prev]")) {
            if (currentPage > 1) {
                const targetPage = currentPage - 1;
                runPage({page: targetPage, cursor: cursorHistory[targetPage] || "", sample: currentMode === "sample"});
            }
            return;
        }

        const diagraphToggle = event.target.closest("[data-diagraph-toggle]");
        if (diagraphToggle) {
            const shell = diagraphToggle.closest(".diagraph-panel-shell");
            const panel = shell && shell.querySelector("[data-diagraph-panel]");
            const pairId = diagraphToggle.dataset.pairId || "";
            if (!panel) {
                return;
            }
            const isOpening = panel.hidden;
            panel.hidden = !panel.hidden;
            if (shell) {
                shell.classList.toggle("is-open", !panel.hidden);
            }
            diagraphToggle.textContent = panel.hidden ? "生成跨句图谱" : "收起跨句图谱";
            if (isOpening) {
                loadDiagraph(panel, pairId, panel.dataset.window || "pair");
            }
            return;
        }

        const windowButton = event.target.closest("[data-diagraph-window]");
        if (windowButton) {
            const panel = windowButton.closest("[data-diagraph-panel]");
            const shell = windowButton.closest(".diagraph-panel-shell");
            const toggle = shell && shell.querySelector("[data-diagraph-toggle]");
            const pairId = toggle && toggle.dataset.pairId;
            if (!panel || !pairId) {
                return;
            }
            panel.querySelectorAll("[data-diagraph-window]").forEach((button) => button.classList.remove("active"));
            windowButton.classList.add("active");
            loadDiagraph(panel, pairId, windowButton.dataset.diagraphWindow || "pair");
            return;
        }

        const copyButton = event.target.closest("[data-diagraph-copy]");
        if (copyButton) {
            const panel = copyButton.closest("[data-diagraph-panel]");
            const data = panel && panel.diagraphData;
            if (!data || !navigator.clipboard) {
                return;
            }
            navigator.clipboard.writeText(serializeDiagraphText(data));
        }
    });

    document.addEventListener("toggle", (event) => {
        const details = event.target.closest(".original-context");
        if (details && details.open) {
            loadContext(details);
        }
    }, true);

    /* ========== Initialization ========== */
    resetPaging();
    runPage({sample: form.dataset.autoSearch !== "1" || getKeyword().length < 2});
})();
