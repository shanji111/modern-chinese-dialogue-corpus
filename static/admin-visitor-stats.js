(function () {
    "use strict";

    const chart = document.querySelector("[data-visitor-chart]");
    if (!chart) {
        return;
    }

    const source = document.getElementById(chart.dataset.chartSource);
    const svg = chart.querySelector("svg");
    const emptyState = chart.querySelector("[data-chart-empty]");
    let points = [];

    try {
        points = JSON.parse(source.textContent || "[]");
    } catch (error) {
        points = [];
    }

    if (!points.length) {
        svg.hidden = true;
        emptyState.hidden = false;
        return;
    }

    const namespace = "http://www.w3.org/2000/svg";
    const width = 960;
    const height = 280;
    const padding = { top: 24, right: 24, bottom: 42, left: 48 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const maxValue = Math.max(1, ...points.map((point) => Number(point.peak_online) || 0));

    function addElement(name, attributes, text) {
        const element = document.createElementNS(namespace, name);
        Object.entries(attributes || {}).forEach(([key, value]) => {
            element.setAttribute(key, String(value));
        });
        if (text !== undefined) {
            element.textContent = text;
        }
        svg.appendChild(element);
        return element;
    }

    for (let index = 0; index <= 4; index += 1) {
        const y = padding.top + (plotHeight / 4) * index;
        const value = Math.round(maxValue * (1 - index / 4));
        addElement("line", {
            x1: padding.left,
            y1: y,
            x2: width - padding.right,
            y2: y,
            class: "visitor-chart-grid-line"
        });
        addElement("text", {
            x: padding.left - 10,
            y: y + 4,
            "text-anchor": "end",
            class: "visitor-chart-axis-label"
        }, value);
    }

    const coordinates = points.map((point, index) => {
        const x = padding.left + (points.length === 1 ? 0 : (index / (points.length - 1)) * plotWidth);
        const y = padding.top + plotHeight - ((Number(point.online) || 0) / maxValue) * plotHeight;
        return { x, y, point };
    });

    const areaPath = [
        `M ${coordinates[0].x} ${padding.top + plotHeight}`,
        ...coordinates.map((item) => `L ${item.x} ${item.y}`),
        `L ${coordinates[coordinates.length - 1].x} ${padding.top + plotHeight}`,
        "Z"
    ].join(" ");
    addElement("path", { d: areaPath, class: "visitor-chart-area" });
    addElement("polyline", {
        points: coordinates.map((item) => `${item.x},${item.y}`).join(" "),
        class: "visitor-chart-line"
    });

    const labelStep = Math.max(1, Math.ceil((points.length - 1) / 6));
    coordinates.forEach((item, index) => {
        const isLast = index === points.length - 1;
        const isRegularLabel = index % labelStep === 0;
        const tooCloseToLast = !isLast && points.length - 1 - index < labelStep * 0.65;
        if ((!isRegularLabel && !isLast) || tooCloseToLast) {
            return;
        }
        addElement("text", {
            x: item.x,
            y: height - 16,
            "text-anchor": index === 0 ? "start" : (index === points.length - 1 ? "end" : "middle"),
            class: "visitor-chart-axis-label"
        }, item.point.label);
    });

    const latest = coordinates[coordinates.length - 1];
    addElement("circle", {
        cx: latest.x,
        cy: latest.y,
        r: 4,
        class: "visitor-chart-latest-dot"
    });
})();
