import { clearChartInstance, setChartInstance } from "../state.js";
import { escapeHtml } from "../utils.js";

let currentGenreChartType = "treemap";
let currentActiveGenreLabel = null;
let currentGenreScope = "top_10";

function truncateText(str, maxLength = 30) {
    if (!str) return "";
    return str.length > maxLength
        ? str.slice(0, maxLength - 1) + "…"
        : str;
}

function genreToColor(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash % 360);
    return `hsl(${hue}, 60%, 45%)`;
}

function getGradientColor(index, total) {
    if (total <= 1) return "hsl(140, 60%, 45%)";

    const t = index / (total - 1);

    const hueStart = 140;
    const hueEnd = 320;

    const hue = hueStart + (hueEnd - hueStart) * t;

    const lightness = 40 + (Math.sin(t * Math.PI * 4) * 8);

    return `hsl(${hue}, 65%, ${lightness}%)`;
}

export function renderGenres(data, currentSelection) {

    const out = document.getElementById("wsAnalyticsOutput");

    if (!data || !data.top_10) {
        out.innerHTML = `<p style="opacity:0.7;">No genre data.</p>`;
        clearChartInstance();
        return;
    }

    out.innerHTML = `
    <div class="ws-genres-full">

        <span 
            class="ws-panel-help ws-help"
            data-tooltip="This page shows you the most common genres in your selection. Note that Spotify does not always provide a genre and many are very broad.
            
            Concentration - How concentrated the selection is around its most frequent genres.

            Top Genre - The most common genre and its percentage of the selection.

            Dominance Gap - Percentage point difference between the top genre(s) and the next most common genre.

            Avg Tracks / Genre - The average number of tracks that share a genre tag.

            Multi-Genre Tracks - Percentage of tracks that are tagged with more than one genre.

            Most Genre-Dense Track - The track with the most genre tags, and how many it has.
            ">
        Help
        </span>
        
        <div class="ws-header">
            <div class="ws-title">
                Genre Diversity:
                <span class="ws-title-number">${data.diversity_score}</span>
            </div>

            <div class="ws-subrow">
                <div class="ws-selection">
                    ${
                        currentSelection === "combined"
                            ? `
                                <span class="ws-selection-name">All Selected</span>
                                <span class="ws-selection-meta">${data.track_count} tracks • ${data.unique_genres} genres</span>
                              `
                            : `
                                <span class="ws-selection-name">
                                    ${escapeHtml(data.playlist_name || "")}
                                </span>
                                <span class="ws-selection-meta">${data.track_count} tracks • ${data.unique_genres} genres</span>
                              `
                    }
                </div>

                <div class="ws-controls-row">
                    <button id="genreScopeToggle" class="ws-scope-btn">
                        Top 10
                    </button>

                    <button id="genreChartToggle" class="ws-swap-btn">
                        Swap Style
                    </button>
                </div>

            </div>
        </div>

        <div class="ws-genres-layout">
            <div class="ws-genres-panel">

                <div class="ws-genres-card ws-release-dominant">
                    <div class="ws-genres-label">Concentration</div>
                    <div class="ws-genres-value">${data.concentration}</div>
                </div>

                <div class="ws-genres-card">
                    <div class="ws-genres-label">Top Genre</div>
                    <div class="ws-genres-value">
                        ${escapeHtml(data.top_genre)}
                        <span>(${data.top_genre_pct}%)</span>
                    </div>
                </div>

                <div class="ws-genres-card">
                    <div class="ws-genres-label">Dominance Gap</div>
                    <div class="ws-genres-value">${data.dominance_gap}%</div>
                </div>

                <div class="ws-genres-card">
                    <div class="ws-genres-label">Avg Tracks / Genre</div>
                    <div class="ws-genres-value">${data.avg_tracks_per_genre}</div>
                </div>

                <div class="ws-genres-card">
                    <div class="ws-genres-label">Multi-Genre Tracks</div>
                    <div class="ws-genres-value">${data.multi_genre_track_pct}%</div>
                </div>

                <div class="ws-genres-card">
                    <div class="ws-genres-label">Most Genre-Dense Track</div>
                    <div class="ws-genres-value">
                        <a href="https://open.spotify.com/track/${data.max_genre_track_id}" target="_blank">
                            ${truncateText(escapeHtml(data.max_genre_track_name || ""), 30)}
                        </a>
                        <span>(${data.max_genres_on_track})</span>
                    </div>
                </div>

            </div>

            <div class="ws-genres-right">
                <div class="ws-genres-chart">
                    <canvas id="wsChart"></canvas>
                </div>

                <div class="ws-genres-active ws-genres-card">
                    <div class="ws-genres-active-row">
                        <div class="ws-genre-active-icon"></div>

                        <div class="ws-genres-active-info">
                            <div class="ws-genres-active-name"></div>
                            <div class="ws-genres-active-meta"></div>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    </div>
    `;

    renderGenreChart(data);

    const toggle = document.getElementById("genreChartToggle");
    if (toggle) {
        toggle.onclick = () => {
            currentGenreChartType =
                currentGenreChartType === "bar" ? "treemap" : "bar";

            // 👇 update visibility here too
            const scopeToggle = document.getElementById("genreScopeToggle");
            if (scopeToggle) {
                scopeToggle.style.display =
                    currentGenreChartType === "bar" ? "none" : "inline-block";
            }

            renderGenreChart(data);
        };
    }

    const scopeToggle = document.getElementById("genreScopeToggle");

    if (scopeToggle) {
        scopeToggle.style.display =
            currentGenreChartType === "bar" ? "none" : "inline-block";
    }

    if (scopeToggle) {
        scopeToggle.onclick = () => {
            currentGenreScope =
                currentGenreScope === "top_10" ? "all" : "top_10";

            scopeToggle.textContent =
                currentGenreScope === "top_10" ? "Top 10" : "All";

            renderGenreChart(data);
        };
    }
}

function renderGenreChart(data) {

    clearChartInstance();

    const canvas = document.getElementById("wsChart");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    const activeIcon = document.querySelector(".ws-genre-active-icon");
    const activeName = document.querySelector(".ws-genres-active-name");
    const activeMeta = document.querySelector(".ws-genres-active-meta");

    const sourceData =
        currentGenreChartType === "bar"
            ? data.top_10
            : (
                currentGenreScope === "all"
                    ? (data.display_genres || data.top_10)
                    : data.top_10
            );

    const treeData = sourceData.map((g, i) => ({
        label: g.genre,
        value: g.count,
        color: getGradientColor(i, sourceData.length)
    }));

    function setActiveGenre(item) {
        if (!item || !activeIcon || !activeName || !activeMeta) return;

        currentActiveGenreLabel = item.label;

        const color = item.color;

        activeIcon.style.background = color;
        activeName.textContent = item.label;

        const percent = data.track_count
            ? ((item.value / data.track_count) * 100).toFixed(1)
            : 0;

        activeMeta.textContent =
            `Appears on ${item.value} tracks • ${percent}% of selection`;

        activeName.style.setProperty("--genresColor", color);
    }

    // =========================
    // BAR CHART
    // =========================
    if (currentGenreChartType === "bar") {

        const labels = treeData.map(a => a.label);
        const values = treeData.map(a => a.value);
        const colors = treeData.map(d => d.color);

        const chart = new Chart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderRadius: 4,
                    borderWidth: 1,
                    borderColor: "rgba(0,0,0,0.35)",
                    hoverBorderWidth: 2,
                    hoverBorderColor: "#1DB954"
                }]
            },
            options: {
                indexAxis: "y",
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { color: "rgba(255,255,255,0.7)" },
                        grid: { color: "rgba(255,255,255,0.06)" }
                    },
                    y: {
                        ticks: { color: "rgba(255,255,255,0.85)" },
                        grid: { display: false }
                    }
                },
                onHover: (event, activeEls) => {
                    if (!activeEls?.length) return;

                    const index = activeEls[0].index;
                    const item = treeData[index];
                    if (!item) return;

                    setActiveGenre(item);
                }
            }
        });

        setChartInstance(chart);

        if (treeData.length) {
            let target = treeData[0];

            if (currentActiveGenreLabel) {
                const match = treeData.find(
                    a => a.label === currentActiveGenreLabel
                );
                if (match) target = match;
            }

            setActiveGenre(target);
        }

        return;
    }

    // =========================
    // TREEMAP
    // =========================

    const chart = new Chart(ctx, {
        type: "treemap",
        data: {
            datasets: [{
                tree: treeData,
                key: "value",
                groups: ["label"],
                spacing: 3,
                borderWidth: 2,
                borderColor: "rgba(0,0,0,0.35)",

                hoverBorderWidth: 2,
                hoverBorderColor: "#1DB954",

                backgroundColor(context) {
                    const i = context.dataIndex;
                    return treeData[i]?.color || "#1DB954";
                }
            }]
        },
        options: {
            maintainAspectRatio: false,
            animation: {
                duration: 400,
                easing: "easeOutCubic"
            },
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            onHover: (evt, activeEls) => {
                if (!activeEls?.length) return;

                const el = activeEls[0]?.element;
                const raw = el?.$context?.raw;

                const label =
                    raw?._data?.label ||
                    raw?.g ||
                    raw?.label;

                if (!label) return;

                const item = treeData.find(t => t.label === label);
                if (!item) return;

                setActiveGenre(item);
            }
        }
    });

    setChartInstance(chart);

    if (treeData.length) {
        setActiveGenre(treeData[0]);
    }
}