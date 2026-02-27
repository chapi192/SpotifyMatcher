import { wsChartInstance, setChartInstance, clearChartInstance } from "./state.js";
import { formatTime } from "./utils.js";

export function renderGenreChart(genreCounts) {
    clearChartInstance();
    if (!genreCounts) return;

    const sorted = Object.entries(genreCounts)
        .sort((a,b)=>b[1]-a[1])
        .slice(0,10);

    const labels = sorted.map(g => g[0]);
    const values = sorted.map(g => g[1]);

    const ctx = document.getElementById("wsChart").getContext("2d");

    setChartInstance(new Chart(ctx, {
        type: "bar",
        data: { labels, datasets: [{ data: values }] },
        options: { indexAxis: "y", plugins: { legend: { display: false } } }
    }));
}

export function buildHistogram(ctx, labels, values) {

    return new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: "rgba(29,185,84,0.8)",
                borderColor: "rgba(29,185,84,1)",
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            devicePixelRatio: window.devicePixelRatio || 1,

            animation: {
                duration: 350,
                easing: "easeOutCubic"
            },

            layout: {
                padding: {
                top: 0,
                bottom: 0
                }
            },

            plugins: {
                legend: { display: false }
            },

            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { color: "rgba(255,255,255,0.7)" },
                    grid: { color: "rgba(255,255,255,0.05)" },
                    grace: 0
                },
                x: {
                    ticks: { color: "rgba(255,255,255,0.7)" },
                    grid: { color: "rgba(255,255,255,0.03)" }
                }
            }
        }
    });
}

export function renderHistogram(durations) {

    const bucketSize = 30;
    const buckets = {};

    durations.forEach(sec => {
        const bucket = Math.floor(sec / bucketSize) * bucketSize;
        buckets[bucket] = (buckets[bucket] || 0) + 1;
    });

    const sortedBuckets = Object.keys(buckets)
        .map(Number)
        .sort((a,b)=>a-b);

    const labels = sortedBuckets.map(start => {
        const end = start + bucketSize;
        return `${formatTime(start)}–${formatTime(end)}`;
    });

    const values = sortedBuckets.map(k => buckets[k]);

    const ctx = document.getElementById("wsChart").getContext("2d");
    const inner = document.getElementById("wsAnalyticsOutput");

    // If chart exists → shrink first
    if (wsChartInstance) {

        wsChartInstance.data.datasets[0].data =
            wsChartInstance.data.datasets[0].data.map(() => 0);

        wsChartInstance.update();

        setTimeout(() => {

            inner.classList.add("fade-out");

            setTimeout(() => {

                clearChartInstance();

                setChartInstance(
                    buildHistogram(ctx, labels, values)
                );

                inner.classList.remove("fade-out");
                inner.classList.add("fade-in");

                setTimeout(() => {
                    inner.classList.remove("fade-in");
                }, 120);

            }, 80);

        }, 120);

        return;
    }

    // First render case
    clearChartInstance();
    setChartInstance(
        buildHistogram(ctx, labels, values)
    );
}

export function renderScatter(durations) {

    const points = durations.map((sec, i) => ({
        x: i + 1,
        y: sec
    }));

    const ctx = document.getElementById("wsChart").getContext("2d");

    clearChartInstance();
    setChartInstance(new Chart(ctx, {
        type: "scatter",
        data: {
            datasets: [{
                data: points
            }]
        },
        options: {
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    title: { display: true, text: "Track Index" }
                },
                y: {
                    title: { display: true, text: "Length (seconds)" }
                }
            }
        }
    }));
}

export function renderPopularityHistogram(values) {

    const bins = Array(10).fill(0);

    values.forEach(v => {
        const n = Number(v);
        if (!Number.isFinite(n)) return;
        const idx = Math.min(Math.floor(n / 10), 9);
        bins[idx]++;
    });

    const labels = [
        "0–9","10–19","20–29","30–39","40–49",
        "50–59","60–69","70–79","80–89","90–100"
    ];

    const ctx = document.getElementById("wsChart").getContext("2d");

    const buildChart = () => {
        const barColors = bins.map((_, index) => {

            const progress = index / 9;

            const start = { r: 255, g: 255, b: 255, a: 0.25 };
            const end   = { r: 29,  g: 185, b: 84,  a: 1.0 };

            const r = Math.round(start.r + (end.r - start.r) * progress);
            const g = Math.round(start.g + (end.g - start.g) * progress);
            const b = Math.round(start.b + (end.b - start.b) * progress);
            const a = start.a + (end.a - start.a) * progress;

            return `rgba(${r},${g},${b},${a})`;
        });

        setChartInstance(new Chart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    data: bins,
                    backgroundColor: barColors,
                    borderWidth: 0,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 400,
                    easing: "easeOutCubic"
                },
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { color: "rgba(255,255,255,0.6)" },
                        grid: { color: "rgba(255,255,255,0.03)" }
                    },
                    x: {
                        ticks: { color: "rgba(255,255,255,0.6)" },
                        grid: { color: "rgba(255,255,255,0.02)" }
                    }
                }
            }
        }));

    };

    // 🔥 If chart exists → shrink first
    if (wsChartInstance) {

        wsChartInstance.data.datasets[0].data =
            wsChartInstance.data.datasets[0].data.map(() => 0);

        wsChartInstance.update();

        setTimeout(() => {
            clearChartInstance();
            buildChart();
        }, 250);

        return;
    }

    clearChartInstance();
    buildChart();
}