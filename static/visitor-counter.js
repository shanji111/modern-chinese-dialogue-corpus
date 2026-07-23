(function () {
    "use strict";

    const counter = document.querySelector("[data-visitor-counter]");
    if (!counter) {
        return;
    }

    const endpoint = counter.dataset.endpoint;
    const onlineElement = counter.querySelector("[data-visitor-online]");
    const totalElement = counter.querySelector("[data-visitor-total]");
    const errorElement = counter.querySelector("[data-visitor-error]");
    const numberFormatter = new Intl.NumberFormat("zh-CN");
    let requestInProgress = false;

    async function refreshVisitorStats() {
        if (requestInProgress || document.visibilityState === "hidden") {
            return;
        }
        requestInProgress = true;

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: {
                    "Accept": "application/json",
                    "X-Requested-With": "fetch"
                },
                credentials: "same-origin",
                cache: "no-store",
                keepalive: true
            });
            if (!response.ok) {
                throw new Error("Visitor statistics request failed");
            }

            const data = await response.json();
            if (data.ok !== true || !Number.isFinite(data.online) || !Number.isFinite(data.total)) {
                throw new Error("Visitor statistics response is invalid");
            }

            onlineElement.textContent = numberFormatter.format(data.online);
            totalElement.textContent = numberFormatter.format(data.total);
            errorElement.hidden = true;
            counter.classList.remove("visitor-counter-unavailable");
            counter.setAttribute("aria-busy", "false");
            counter.title = `在线人数按近 ${data.window_seconds} 秒内活跃浏览器估算；匿名标识用于访客去重，安全日志会按隐私说明短期记录 IP`;
        } catch (error) {
            errorElement.hidden = false;
            counter.classList.add("visitor-counter-unavailable");
            counter.setAttribute("aria-busy", "false");
        } finally {
            requestInProgress = false;
        }
    }

    refreshVisitorStats();
    window.setInterval(refreshVisitorStats, 30000);
    document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible") {
            refreshVisitorStats();
        }
    });
})();
