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
    const showcaseKey = new URLSearchParams(window.location.search).get("showcase");
    const humanConsensusShowcaseMode = showcaseKey === "human-consensus-bert-audit";

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
                summary.textContent = `分析流程：规则提取结构关系，BERT 用于评估六类关系置信度；当前显示 ${count} 条`;
            }
            if (range) {
                range.textContent = "模型辅助分析";
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
        return String(value === null || value === undefined ? "" : value)
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
    const mechanismNames = {
        reproduction: "重现",
        parallelism: "平行",
        selective_reuse: "选择",
        repair: "修正",
        contrast: "对比",
        analogy_candidate: "类比",
    };

    function markEvidence(text, evidence) {
        let rendered = escapeHtml(text);
        (evidence || []).forEach((fragment) => {
            const escapedFragment = escapeHtml(fragment);
            if (escapedFragment) {
                rendered = rendered.replace(escapedFragment, `<mark>${escapedFragment}</mark>`);
            }
        });
        return rendered;
    }

    function getBertAudit(row) {
        const ordered = ["reproduction", "parallelism", "selective_reuse", "repair", "contrast", "analogy_candidate"];
        const labels = row.humanLabels || [];
        const probabilities = row.bertProbabilities || [];
        const thresholds = row.bertThresholds || [];
        if (!probabilities.length || !thresholds.length) {
            return {available: false, supported: [], predicted: [], exact: false};
        }
        const supported = labels.filter((key) => {
            const index = ordered.indexOf(key);
            return index >= 0 && Number(probabilities[index]) >= Number(thresholds[index]);
        });
        const predicted = ordered.filter((key, index) => Number(probabilities[index]) >= Number(thresholds[index]));
        return {
            available: true,
            supported,
            predicted,
            exact: labels.length === predicted.length && labels.every((key) => predicted.includes(key)),
        };
    }

    function renderConsensusTags(row) {
        if (!(row.humanLabels || []).length) {
            return '<span class="consensus-tag is-uncertain">人工共识：未作类别判定</span>';
        }
        return row.humanLabels.map((key) =>
            `<span class="consensus-tag mechanism-${escapeHtml(key)}">人工共识：${escapeHtml(mechanismNames[key] || key)}</span>`
        ).join("");
    }

    function renderHumanConsensusCard(row) {
        const isUncertain = row.humanStatus === "uncertain";
        const audit = getBertAudit(row);
        const labels = row.humanLabels || [];
        const supportPercent = audit.available && labels.length ? Math.round((audit.supported.length / labels.length) * 100) : 0;
        const predictedLabels = audit.predicted.map((key) => mechanismNames[key] || key).join("、");
        const bertText = !audit.available
            ? `未评分：人工双标共识保留 uncertain。${escapeHtml(row.uncertaintyReason || "")}`
            : `人工标签支持 ${audit.supported.length}/${labels.length}；模型触发：${escapeHtml(predictedLabels || "无")}${audit.exact ? "；六类集合与人工一致。" : "；模型差异不改变人工最终判定。"}`;
        const humanText = isUncertain
            ? `A/B 一致保留 uncertain：${escapeHtml(row.uncertaintyReason || row.humanNote)}`
            : "A/B 对关系、六类标签、证据与说明完全一致。";
        return `
            <article class="resonance-result is-graph-showcase consensus-showcase-card">
                <div class="resonance-result-meta">
                    <b>人工共识案例 ${escapeHtml(row.rank)} · ${escapeHtml(row.annotationId)}</b>
                    <span>${escapeHtml(row.dataset)} · ${escapeHtml(row.source)}</span>
                    <span class="graph-showcase-badge ${isUncertain ? "is-uncertain" : ""}">${isUncertain ? "人工共识：uncertain" : "人工双标共识"}</span>
                </div>
                <div class="consensus-tags">${renderConsensusTags(row)}</div>
                <div class="resonance-explanation">${isUncertain ? "待上下文核验：不强行入图" : "跨轮共鸣：已确认入图"}</div>
                <div class="turn-pair" aria-label="相邻话轮与证据对应">
                    <section><div class="turn-label">A · ${escapeHtml(row.speakerA)}</div><div class="turn-text">${markEvidence(row.turnA, row.evidenceA)}</div></section>
                    <section><div class="turn-label">B · ${escapeHtml(row.speakerB)}</div><div class="turn-text">${markEvidence(row.turnB, row.evidenceB)}</div></section>
                </div>
                <div class="consensus-audit-grid">
                    <section class="consensus-audit-card"><strong>人工双标共识</strong><p>${humanText}</p><p>${escapeHtml(row.humanNote || "")}</p></section>
                    <section class="consensus-audit-card consensus-bert-card"><strong>离线 BERT 辅助核验（不改判）</strong><p>${bertText}</p>${audit.available ? `<div class="consensus-confidence" aria-label="BERT 对人工标签支持 ${supportPercent}%"><i style="width:${supportPercent}%"></i></div>` : ""}</section>
                </div>
            </article>`;
    }

    function renderHumanConsensusShowcase() {
        const rows = Array.isArray(window.HUMAN_CONSENSUS_SHOWCASE_20260726)
            ? window.HUMAN_CONSENSUS_SHOWCASE_20260726
            : [];
        currentMode = "showcase";
        document.body.classList.add("is-human-consensus-showcase");
        if (summary) {
            summary.innerHTML = `<strong>人工双标共识展示</strong>：24 条文学对话；23 条已判定、1 条保留 uncertain；BERT 仅作辅助核验。`;
        }
        if (range) {
            range.textContent = "人工双标共识 · BERT 辅助核验 · 不影响普通检索";
        }
        if (pagination) {
            pagination.hidden = true;
        }
        list.innerHTML = `
            <section class="human-consensus-notice">
                <strong>展示说明</strong>
                <span>本页保留旧六类分类，逐条呈现 A/B 人工双标一致的标签、证据与说明；离线 BERT 只显示辅助核验，不自动改判、不写回语料库，也不改变普通检索排序。</span>
                <a href="${escapeHtml(window.location.pathname)}">返回普通对话句法检索</a>
            </section>
            ${rows.map(renderHumanConsensusCard).join("")}
        `;
    }

    function columnRangeMembers(columnText, columns) {
        const parts = String(columnText || "").split("-");
        const start = columns.indexOf(parts[0]);
        const end = columns.indexOf(parts[parts.length - 1]);
        if (start < 0) {
            return [];
        }
        return columns.slice(start, Math.max(start, end) + 1);
    }

    function buildColumnEvidence(data) {
        const evidence = new Map();
        (data.affordances || []).forEach((item) => {
            columnRangeMembers(item.column, data.columns || []).forEach((column) => {
                if (!evidence.has(column)) {
                    evidence.set(column, new Set());
                }
                (item.mechanism_keys || []).forEach((key) => evidence.get(column).add(key));
            });
        });
        return evidence;
    }

    function primaryMechanism(keys) {
        const ordered = ["reproduction", "parallelism", "selective_reuse", "repair", "contrast", "analogy_candidate"];
        return ordered.find((key) => keys && keys.has(key)) || "";
    }

    function renderBertCalibration(data) {
        const calibration = data.bert_calibration || {};
        const summary = data.mechanism_summary || [];
        if (!calibration.available) {
            return `
                <section class="diagraph-calibration is-unavailable">
                    <div>
                        <div class="diagraph-calibration-title">BERT 模型作用 <span>关系置信度评估</span></div>
                        <p>模型对相邻话轮进行语义编码，输出重现、平行、选择、修正、对比和类比六类关系的置信度，为图谱提供一致性校验和人工复核线索。</p>
                    </div>
                    <span class="diagraph-calibration-state">模型辅助分析</span>
                </section>
            `;
        }
        const cards = summary.map((item) => {
            const probability = item.bert_probability === null || item.bert_probability === undefined
                ? 0
                : Number(item.bert_probability);
            const percent = Math.round(probability * 100);
            const stateLabels = {
                joint: "规则与模型一致",
                rule: "规则识别",
                bert_review: "模型提示复核",
                none: "未识别",
            };
            return `
                <div class="diagraph-mechanism-card state-${escapeHtml(item.support_state || "none")}">
                    <div class="diagraph-mechanism-head">
                        <strong>${escapeHtml(item.label || mechanismNames[item.key] || item.key)}</strong>
                        <span>${escapeHtml(stateLabels[item.support_state] || "未触发")}</span>
                    </div>
                    <div class="diagraph-confidence-track" aria-label="模型置信度 ${percent}%">
                        <i style="width:${Math.max(0, Math.min(100, percent))}%"></i>
                    </div>
                    <div class="diagraph-mechanism-meta">
                        <span>模型置信度 ${percent}%</span>
                        <span>规则证据 ${escapeHtml(item.rule_support || 0)} 条</span>
                    </div>
                </div>
            `;
        }).join("");
        return `
            <section class="diagraph-calibration">
                <div class="diagraph-calibration-header">
                    <div>
                        <div class="diagraph-calibration-title">BERT 模型判别 <span>关系置信度评估</span></div>
                        <p>模型对相邻话轮进行语义编码，评估重现、平行、选择、修正、对比和类比六类关系的置信度，并与规则证据交叉校验。</p>
                    </div>
                    <span class="diagraph-calibration-state">模型辅助分析</span>
                </div>
                <div class="diagraph-mechanism-grid">${cards}</div>
            </section>
        `;
    }

    function renderDiagraphGrid(data) {
        const columnEvidence = buildColumnEvidence(data);
        const headers = data.columns.map((column) => {
            const keys = columnEvidence.get(column);
            const mechanism = primaryMechanism(keys);
            const relationLabel = mechanism ? mechanismNames[mechanism] : "";
            return `
                <th class="${mechanism ? `has-relation mechanism-${mechanism}` : ""}">
                    <span>${escapeHtml(column)}</span>
                    ${relationLabel ? `<small>${escapeHtml(relationLabel)}</small>` : ""}
                </th>
            `;
        }).join("");
        const rows = (data.grid || []).map((row) => {
            const cells = data.columns.map((column) => {
                const value = (row.cells || {})[column] || "";
                const keys = columnEvidence.get(column);
                const mechanism = primaryMechanism(keys);
                const classes = [
                    value ? "filled" : "",
                    mechanism ? "has-relation" : "",
                    mechanism ? `mechanism-${mechanism}` : "",
                ].filter(Boolean).join(" ");
                return `<td class="${classes}">${value ? `<span>${escapeHtml(value)}</span>` : ""}</td>`;
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
                <div class="diagraph-block-heading">
                    <div>
                        <div class="diagraph-block-title">跨话轮纵栏图谱</div>
                        <p>同一纵栏表示程序识别到的复现、映射或回应位置；彩色轨道对应下方关系证据。</p>
                    </div>
                    <span>${escapeHtml((data.grid || []).length)} 话轮 · ${escapeHtml((data.columns || []).length)} 纵栏</span>
                </div>
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
        const cards = items.length ? items.map((item) => {
            const mechanisms = (item.mechanism_keys || []).map((key) => mechanismNames[key] || key);
            const mappings = String(item.mapping || "").split("：").filter(Boolean);
            const mappingHtml = mappings.length > 1
                ? mappings.map((value) => `<span>${escapeHtml(value)}</span>`).join("<b>→</b>")
                : `<span>${escapeHtml(item.mapping || "未提取")}</span>`;
            const evidenceLabel = item.evidence_state === "joint" ? "规则 + BERT 联合支持" : "规则证据";
            return `
                <article class="diagraph-relation-card evidence-${escapeHtml(item.evidence_state || "rule")}">
                    <div class="diagraph-relation-topline">
                        <span class="diagraph-column-badge">纵栏 ${escapeHtml(item.column || "")}</span>
                        <span class="diagraph-relation-badge">${escapeHtml(item.relation || "待归类")}</span>
                        <span class="diagraph-evidence-badge">${escapeHtml(evidenceLabel)}</span>
                    </div>
                    <div class="diagraph-mapping-flow">${mappingHtml}</div>
                    <p>${escapeHtml(item.description || "")}</p>
                    <div class="diagraph-mechanism-tags">
                        ${mechanisms.map((label) => `<span>${escapeHtml(label)}</span>`).join("")}
                    </div>
                </article>
            `;
        }).join("") : `<div class="diagraph-empty-evidence">当前窗口未识别出可归纳的结构关系，可结合上下文人工校订。</div>`;
        return `
            <section class="diagraph-block">
                <div class="diagraph-block-heading">
                    <div>
                        <div class="diagraph-block-title">纵栏关系说明</div>
                        <p>保留旧版关系名称，并将“纵栏—映射—关系—说明”改成更易读的证据卡。</p>
                    </div>
                    <span>${escapeHtml(items.length)} 条关系</span>
                </div>
                <div class="diagraph-relation-list">${cards}</div>
            </section>
        `;
    }

    function renderDiagraphPayload(data) {
        return `
            ${renderBertCalibration(data)}
            ${renderDiagraphGrid(data)}
            ${renderAffordances(data)}
        `;
    }

    /* ========== Diagraph Export / Copy ========== */
    function serializeDiagraphText(data) {
        const lines = [];
        lines.push("跨句图谱");
        if (data.notice) {
            lines.push(data.notice);
        }
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
        lines.push("");
        lines.push("BERT 关系置信度（模型辅助判别）");
        lines.push((data.bert_calibration || {}).notice || "当前未返回模型分数，图谱仅显示规则证据。");
        lines.push(["机制", "概率", "阈值", "模型建议", "规则证据数"].join("\t"));
        const summaryByKey = new Map((data.mechanism_summary || []).map((item) => [item.key, item]));
        ((data.bert_calibration || {}).labels || []).forEach((item) => {
            const summaryItem = summaryByKey.get(item.key) || {};
            lines.push([
                item.label || item.key || "",
                item.probability === undefined ? "" : item.probability,
                item.threshold === undefined ? "" : item.threshold,
                item.suggested ? "是" : "否",
                summaryItem.rule_support || 0,
            ].join("\t"));
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
    if (humanConsensusShowcaseMode) {
        renderHumanConsensusShowcase();
        return;
    }
    resetPaging();
    runPage({sample: form.dataset.autoSearch !== "1" || getKeyword().length < 2});
})();
