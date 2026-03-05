import { clearChartInstance, setChartInstance, wsChartInstance } from "../state.js";

let currentReleaseChartType = "bar";
let currentActiveLabel = null;

function getDecadeColor(index, total) {

    const t = index / Math.max(total - 1, 1);

    const r = Math.round(40);
    const g = Math.round(120 + t * 80);
    const b = Math.round(200 - t * 120);

    return `rgb(${r},${g},${b})`;
}

function formatBucketLabel(label, mode) {

    const year = Number(label);

    if (mode === "year") {
        return `${year}`;
    }

    if (mode === "decade") {
        return `${year}s`;
    }

    // if you later add 5-year grouping:
    if (mode === "five") {
        return `${year}–${year + 4}`;
    }

    return label;
}

function getTimeGrouping(data) {

    const yearCounts = data.year_counts || {};
    const years = Object.keys(yearCounts);

    if (years.length <= 60) {
        return {
            mode: "year",
            labels: years
                .map(Number)
                .sort((a, b) => a - b)
                .map(String),
            values: null // computed later
        };
    }

    // fallback to decades
    const decadeCounts = data.decade_counts || {};

    return {
        mode: "decade",
        labels: Object.keys(decadeCounts)
            .sort(),
        values: null
    };
}

function buildTimeSeries(data) {

    const grouping = getTimeGrouping(data);

    let labels;
    let values;

    if (grouping.mode === "year") {

        labels = grouping.labels;

        values = labels.map(y => data.year_counts[y]);

    } else {

        labels = grouping.labels;

        values = labels.map(d => data.decade_counts[d]);
    }

    return {
        mode: grouping.mode,
        labels,
        values
    };
}

function computeDominantEra(data) {

    const decades = data.decade_counts || {};
    const entries = Object.entries(decades);

    if (!entries.length) return null;

    let max = entries[0];

    for (let i = 1; i < entries.length; i++) {
        if (entries[i][1] > max[1]) {
            max = entries[i];
        }
    }

    return {
        decade: Number(max[0]),
        count: max[1]
    };
}

function computeDistribution(values, total) {
    if (!values.length || !total) return "Balanced";

    const dominant = Math.max(...values);
    const pct = dominant / total;

    if (pct > 0.55) return "Precise";
    if (pct > 0.35) return "Focused";
    if (pct > 0.20) return "Balanced";
    return "Diverse";
}

function computeGenerationalLean(label, mode) {

    let midYear;

    if (mode === "year") {
        midYear = Number(label);
    } else {
        midYear = Number(label) + 5;
    }

    if (midYear < 1980) return "Boomer";
    if (midYear < 2000) return "Gen X";
    if (midYear < 2015) return "Millennial";
    return "Gen Z";
}

export function renderReleaseYears(data, currentSelection) {

    const out = document.getElementById("wsAnalyticsOutput");

    const existing = out.querySelector(".ws-release-full");

    if (!data || !data.decade_counts) {
        out.innerHTML = `<p style="opacity:0.7;">No release data.</p>`;
        clearChartInstance();
        return;
    }

    if (existing) {
        updateReleaseYearsView(data, currentSelection);
        return;
    }

    const { mode, labels, values } = buildTimeSeries(data);

    function setActive(index) {

        const label = labels[index];
        const count = values[index];
        const pct = ((count / total) * 100).toFixed(1);

        currentActiveLabel = label;

        activeTitle.textContent = formatBucketLabel(label, mode);
        activeTitle.style.color = getDecadeColor(index, labels.length);
        activeMeta.textContent =
            `${count} tracks • ${pct}% of playlist`;
    }

    const total = data.track_count || 1;

    const dominant = computeDominantEra(data);
    const distribution = computeDistribution(values, total);

    let generation = "-";

    if (dominant) {
        generation = computeGenerationalLean(dominant.decade, "decade");
    }

    out.innerHTML = `
    <div class="ws-release-full">

        <div class="ws-avg-header">

            <div class="ws-avg-title">
                Release Span:
                <span class="ws-avg-inline-number">
                    ${data.oldest_year}–${data.newest_year}
                </span>
            </div>

            <div class="ws-avg-selection">
                ${
                    currentSelection === "combined"
                        ? `
                            <span class="ws-selection-name">
                                All Selected
                            </span>
                            <span class="ws-selection-meta">${data.track_count} tracks</span>
                        `
                        : `
                            <a 
                                href="https://open.spotify.com/playlist/${currentSelection}" 
                                target="_blank"
                                class="ws-selection-name ws-selection-link"
                            >
                                ${data.playlist_name || ""}
                            </a>
                            <span class="ws-selection-meta">${data.track_count} tracks</span>
                        `
                }
            </div>

        </div>

        <div class="ws-release-layout">

            <!-- LEFT SIDE -->
            <div class="ws-release-left">
                <div class="ws-release-chart">
                    <canvas id="wsChart"></canvas>
                </div>
            </div>

            <!-- RIGHT SIDE -->
            <div class="ws-release-right">

                <div class="ws-release-controls">

                    <span 
                        class="ws-panel-help ws-help"
                        data-tooltip="Dominant Era – most commonly appearing decade.\n
Distribution – concentration across decades.
\nGenerational Lean – most represented generation of selection."
                        ">
                        ?
                    </span>

                    <button class="ws-swap-btn" data-type="bar">Bar</button>
                    <button class="ws-swap-btn" data-type="spiral">Spiral</button>
                    <button class="ws-swap-btn" data-type="ring">Ring</button>

                </div>

                <div class="ws-release-panel">

                    <div class="ws-artist-card">
                        <div class="ws-artist-label">Newest</div>
                        <div class="ws-artist-value">
                            ${
                                data.newest_track
                                    ? `<a href="${data.newest_track.url}" target="_blank">
                                        ${data.newest_track.name}
                                    </a> (${data.newest_year})`
                                    : data.newest_year
                            } 
                        </div>
                    </div>

                    <div class="ws-artist-card">
                        <div class="ws-artist-label">Oldest</div>
                        <div class="ws-artist-value">
                            ${
                                data.oldest_track
                                    ? `<a href="${data.oldest_track.url}" target="_blank">
                                        ${data.oldest_track.name}
                                    </a> (${data.oldest_year})`
                                    : data.oldest_year
                            }
                        </div>
                    </div>

                    <div class="ws-artist-card">
                        <div class="ws-artist-label">Dominant Era</div>
                        <div class="ws-artist-value">
                            ${
                                dominant
                                    ? `${dominant.decade}s (${((dominant.count / total) * 100).toFixed(1)}%)`
                                    : "-"
                            }
                        </div>
                    </div>

                    <div class="ws-artist-card">
                        <div class="ws-artist-label">Distribution</div>
                        <div class="ws-artist-value">${distribution}</div>
                    </div>

                    <div class="ws-artist-card">
                        <div class="ws-artist-label">Generational Lean</div>
                        <div class="ws-artist-value">${generation}</div>
                    </div>

                </div>

                <div class="ws-release-active ws-artist-card">
                    <div class="ws-release-active-title"></div>
                    <div class="ws-release-active-meta"></div>
                </div>

            </div>
        </div>
    </div>
    `;

    document.querySelectorAll(".ws-release-controls .ws-swap-btn")
        .forEach(btn => {
            btn.onclick = () => {

                const type = btn.dataset.type;

                if (type === currentReleaseChartType) return;

                currentReleaseChartType = type;

                document.querySelectorAll(".ws-release-controls .ws-swap-btn")
                    .forEach(b => {
                        b.disabled = b.dataset.type === currentReleaseChartType;
                        b.classList.toggle(
                            "ws-btn-active",
                            b.dataset.type === currentReleaseChartType
                        );
                    });

                animateReleaseChartSwap(data);
            };
        });

    updateReleaseButtonState();
    renderReleaseChart(data);
}

function updateReleaseYearsView(data, currentSelection) {

    // Update header numbers
    const spanEl = document.querySelector(".ws-avg-inline-number");
    if (spanEl) {
        spanEl.textContent = `${data.oldest_year}–${data.newest_year}`;
    }

    const { mode, labels, values } = buildTimeSeries(data);

    const selectionEl = document.querySelector(".ws-avg-selection");

    if (selectionEl) {

        selectionEl.innerHTML =
            currentSelection === "combined"
                ? `
                    <span class="ws-selection-name">
                        All Selected
                    </span>
                    <span class="ws-selection-meta">${data.track_count} tracks</span>
                `
                : `
                    <a 
                        href="https://open.spotify.com/playlist/${currentSelection}" 
                        target="_blank"
                        class="ws-selection-name ws-selection-link"
                    >
                        ${data.playlist_name || ""}
                    </a>
                    <span class="ws-selection-meta">${data.track_count} tracks</span>
                `;
    }

    function setActive(index) {

        const label = labels[index];
        const count = values[index];
        const pct = ((count / total) * 100).toFixed(1);

        currentActiveLabel = label;

        activeTitle.textContent = formatBucketLabel(label, mode);
        activeTitle.style.color = getDecadeColor(index, labels.length);
        activeMeta.textContent =
            `${count} tracks • ${pct}% of playlist`;
    }

    const total = data.track_count || 1;

    const dominant = computeDominantEra(data);
    const distribution = computeDistribution(values, total);

    let generation = "-";

    if (dominant) {
        generation = computeGenerationalLean(dominant.decade, "decade");
    }

    const valuesEls = document.querySelectorAll(".ws-release-panel .ws-artist-value");

    if (valuesEls.length >= 5) {

        valuesEls[0].textContent = data.newest_year;
        valuesEls[1].textContent = data.oldest_year;

        valuesEls[2].textContent = dominant
            ? `${dominant.decade}s (${((dominant.count / total) * 100).toFixed(1)}%)`
            : "-";

        valuesEls[3].textContent = distribution;
        valuesEls[4].textContent = generation;
    }

    // Re-render chart only (container remains)
    renderReleaseChart(data);
}

function renderReleaseChart(data) {
    clearChartInstance();

    if (currentReleaseChartType === "bar") {
        renderDecadeBarChart(data);
    }
    else if (currentReleaseChartType === "spiral") {
        renderYearSpiralChart(data);
    }
    else {
        renderRingPlaceholder(data);
    }

    if (!currentActiveLabel) {
        const activeTitle = document.querySelector(".ws-release-active-title");
        const activeMeta = document.querySelector(".ws-release-active-meta");

        activeTitle.textContent = "";
        activeMeta.textContent = "";
    }
}

async function animateReleaseChartSwap(data) {

    if (wsChartInstance) {

        const chart = wsChartInstance;

        // LOCK AXIS if cartesian
        if (chart.scales?.y) {

            const currentMax = chart.scales.y.max;

            chart.options.scales.y.min = 0;
            chart.options.scales.y.max = currentMax;

            chart.update();
        }

        // Animate values down to zero
        chart.data.datasets.forEach(ds => {
            ds.data = ds.data.map(() => 0);
        });

        chart.update();

        await new Promise(resolve => setTimeout(resolve, 300));
    }

    renderReleaseChart(data);
}

function renderDecadeBarChart(data) {

    const ctx = document.getElementById("wsChart").getContext("2d");

    const { mode, labels, values } = buildTimeSeries(data);
    const total = data.track_count || 1;

    const activeTitle = document.querySelector(".ws-release-active-title");
    const activeMeta = document.querySelector(".ws-release-active-meta");

    function setActive(index) {

        const label = labels[index];
        const count = values[index];
        const pct = ((count / total) * 100).toFixed(1);

        currentActiveLabel = label;

        activeTitle.textContent = formatBucketLabel(label, mode);
        activeTitle.style.color = getDecadeColor(index, labels.length);
        activeMeta.textContent =
            `${count} tracks • ${pct}% of playlist`;
    }

    const chart = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: labels.map((_, i) =>
                    getDecadeColor(i, labels.length)
                ),
                borderRadius: 6,
                borderWidth: 1,
                borderColor: "rgba(255,255,255,0.08)",
                hoverBorderWidth: 2,
                hoverBorderColor: "#1DB954"
            }]
        },
        options: {
            maintainAspectRatio: false,
            animation: {
                duration: 350,
                easing: "easeOutCubic"
            },
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { color: "rgba(255,255,255,0.65)" },
                    grid: { color: "rgba(255,255,255,0.05)" }
                },
                x: {
                    ticks: {
                        color: "rgba(255,255,255,0.85)",
                        maxRotation: mode === "year" ? 90 : 0,
                        minRotation: mode === "year" ? 90 : 0
                    },
                    grid: { display: false }
                }
            },
            onHover: (evt, activeEls) => {
                if (!activeEls?.length) return;
                setActive(activeEls[0].index);
            }
        }
    });

    setChartInstance(chart);
    if (labels.length) setActive(0);
}

function renderYearSpiralChart(data) {

    const ctx = document.getElementById("wsChart").getContext("2d");

    const { mode, labels, values } = buildTimeSeries(data);
    const total = data.track_count || 1;

    if (!labels.length) return;

    const activeTitle = document.querySelector(".ws-release-active-title");
    const activeMeta = document.querySelector(".ws-release-active-meta");

    function setActive(index) {

        const label = labels[index];
        const count = values[index];
        const pct = ((count / total) * 100).toFixed(1);

        currentActiveLabel = label;

        activeTitle.textContent = formatBucketLabel(label, mode);
        activeTitle.style.color = getDecadeColor(index, labels.length);
        activeMeta.textContent =
            `${count} tracks • ${pct}% of playlist`;
    }

    const chart = new Chart(ctx, {
        type: "polarArea",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: labels.map((_, i) =>
                    getDecadeColor(i, labels.length)
                ),
                borderWidth: 1,
                borderColor: "rgba(0,0,0,0.3)",
                hoverBorderWidth: 2,
                hoverBorderColor: "#1DB954"
            }]
        },
        options: {
            maintainAspectRatio: false,
            animation: {
                duration: 350,
                easing: "easeOutCubic"
            },
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    ticks: { display: false },
                    grid: { color: "rgba(255,255,255,0.05)" },
                    angleLines: { color: "rgba(255,255,255,0.05)" }
                }
            },
            onHover: (evt, activeEls) => {
                if (!activeEls?.length) return;
                setActive(activeEls[0].index);
            }
        }
    });

    setChartInstance(chart);
    setActive(0);
}

function renderRingPlaceholder(data) {

    const ctx = document.getElementById("wsChart").getContext("2d");

    const { mode, labels, values } = buildTimeSeries(data);
    const total = data.track_count || 1;

    if (!labels.length) return;

    const activeTitle = document.querySelector(".ws-release-active-title");
    const activeMeta = document.querySelector(".ws-release-active-meta");

    function setActive(index) {

        const label = labels[index];
        const count = values[index];
        const pct = ((count / total) * 100).toFixed(1);

        currentActiveLabel = label;

        activeTitle.textContent = formatBucketLabel(label, mode);
        activeTitle.style.color = getDecadeColor(index, labels.length);
        activeMeta.textContent =
            `${count} tracks • ${pct}% of playlist`;
    }

    const chart = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: labels.map((_, i) =>
                    getDecadeColor(i, labels.length)
                ),
                borderWidth: 2,
                borderColor: "rgba(0,0,0,0.35)",
                hoverBorderWidth: 2,
                hoverBorderColor: "#1DB954"
            }]
        },
        options: {
            maintainAspectRatio: false,
            cutout: "72%",
            radius: "88%",
            animation: {
                duration: 350,
                easing: "easeOutCubic"
            },
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            onHover: (evt, activeEls) => {
                if (!activeEls?.length) return;
                setActive(activeEls[0].index);
            }
        }
    });

    setChartInstance(chart);
    setActive(0);
}

function updateReleaseButtonState() {

    document.querySelectorAll(".ws-release-controls .ws-swap-btn")
        .forEach(btn => {

            const isActive = btn.dataset.type === currentReleaseChartType;

            btn.disabled = isActive;

            if (isActive) {
                btn.classList.add("ws-btn-active");
            } else {
                btn.classList.remove("ws-btn-active");
            }
        });
}