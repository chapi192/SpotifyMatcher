import { clearChartInstance, setChartInstance } from "../state.js";
import { escapeHtml } from "../utils.js";
import { wsChartInstance } from "../state.js";

let currentArtistChartType = "bar";
let currentActiveArtistLabel = null;

function truncateText(str, maxLength = 30) {
    if (!str) return "";
    return str.length > maxLength
        ? str.slice(0, maxLength - 1) + "…"
        : str;
}

export function renderArtistFrequency(data, currentSelection) {
    const out = document.getElementById("wsAnalyticsOutput");

    if (!data || !data.top_10) {
        out.innerHTML = `<p style="opacity:0.7;">No artist data.</p>`;
        clearChartInstance();
        return;
    }

    out.innerHTML = `
    <div class="ws-artist-full">
        <div class="ws-avg-header">
            <div class="ws-avg-title">
                Artist Diversity:
                <span class="ws-avg-inline-number">${data.diversity_score}</span>
            </div>

            <div class="ws-artist-header-row">
                <div class="ws-artist-selection-left">
                    ${
                        currentSelection === "combined"
                            ? `
                                <span class="ws-selection-name">All Selected</span>
                                <span class="ws-selection-meta">
                                    ${data.track_count} tracks • ${data.unique_artists} artists
                                </span>
                              `
                            : `
                                <a
                                    href="https://open.spotify.com/playlist/${currentSelection}"
                                    target="_blank"
                                    class="ws-selection-name ws-selection-link"
                                >
                                    ${escapeHtml(data.playlist_name || "")}
                                </a>
                                <span class="ws-selection-meta">
                                    ${data.track_count} tracks • ${data.unique_artists} artists
                                </span>
                              `
                    }
                </div>

                <button id="artistChartToggle" class="ws-swap-btn">
                    Swap Style
                </button>
            </div>
        </div>

        <div class="ws-artist-layout">
            <div class="ws-artist-panel">
                <div class="ws-artist-card">
                    <div class="ws-artist-label">Concentration</div>
                    <div class="ws-artist-value">${data.concentration}</div>
                </div>

                <div class="ws-artist-card">
                    <div class="ws-artist-label">Top Artist</div>
                    <div class="ws-artist-value">
                        <a href="https://open.spotify.com/artist/${data.top_artist_id}" target="_blank">
                            ${escapeHtml(data.top_artist_name)}
                        </a>
                        <span>(${data.dominance_pct}%)</span>
                    </div>
                </div>

                <div class="ws-artist-card">
                    <div class="ws-artist-label">Unique Appearances</div>
                    <div class="ws-artist-value">${data.unique_appearance_pct}%</div>
                </div>

                <div class="ws-artist-card">
                    <div class="ws-artist-label">Avg Tracks / Artist</div>
                    <div class="ws-artist-value">${data.avg_tracks_per_artist}</div>
                </div>

                <div class="ws-artist-card">
                    <div class="ws-artist-label">Multi-Artist Tracks</div>
                    <div class="ws-artist-value">${data.multi_artist_track_pct}%</div>
                </div>

                <div class="ws-artist-card">
                    <div class="ws-artist-label">Max Artists On Track</div>
                    <div class="ws-artist-value">
                        <a href="https://open.spotify.com/track/${data.max_artist_track_id}" target="_blank">
                            ${truncateText(escapeHtml(data.max_artist_track_name), 40)}
                        </a>
                        <span>(${data.max_artists_on_track})</span>
                    </div>
                </div>
            </div>

            <div class="ws-artist-right">
                <div class="ws-artist-chart">
                    <canvas id="wsChart"></canvas>
                    <div class="album-hover-preview"></div>
                </div>

                <div class="ws-artist-active ws-artist-card">
                    <div class="ws-artist-active-row">
                        <div class="ws-artist-active-img"></div>

                        <div class="ws-artist-active-info">
                            <a class="ws-artist-active-name" target="_blank"></a>
                            <div class="ws-artist-active-meta"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    `;

    renderArtistChart(data);
    
    const toggle = document.getElementById("artistChartToggle");
    if (toggle) {
        const toggle = document.getElementById("artistChartToggle");
        if (toggle) {
            toggle.onclick = () => {
                currentArtistChartType = currentArtistChartType === "bar" ? "treemap" : "bar";
                renderArtistChart(data);
            };
        }
    }
}

function renderArtistChart(data) {
    clearChartInstance();

    const canvas = document.getElementById("wsChart");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    const activeImg = document.querySelector(".ws-artist-active-img");
    const activeName = document.querySelector(".ws-artist-active-name");
    const activeMeta = document.querySelector(".ws-artist-active-meta");

    function setActiveArtistFromItem(item, color, imgEl) {
        if (!item || !activeImg || !activeName || !activeMeta) return;

        currentActiveArtistLabel = item.label;  // <--- add this

        activeImg.innerHTML = "";
        if (imgEl) activeImg.appendChild(imgEl.cloneNode());

        activeName.textContent = item.label;
        activeName.href = `https://open.spotify.com/artist/${item.artist_id || ""}`;

        const trackCount = item.value || 0;
        const percent = data.track_count
            ? ((trackCount / data.track_count) * 100).toFixed(1)
            : 0;

        activeMeta.textContent =
            `Appears on ${trackCount} tracks • ${percent}% of playlist`;

        const finalColor = ensureReadableColor(color || "#000000");
        activeName.style.setProperty("--artistColor", finalColor);
    }

    const treeData = (data.top_10 || [])
        .filter(a => a.image_url)
        .map(a => ({
            label: a.artist_name,
            value: a.count,
            image: a.image_url,
            artist_id: a.artist_id
        }));

    const artistColorMap = new Map();
    const imageCache = new Map();

    function extractDominantColor(img) {
        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d");

        const size = 50;
        canvas.width = size;
        canvas.height = size;

        ctx.drawImage(img, 0, 0, size, size);
        const pixels = ctx.getImageData(0, 0, size, size).data;

        const buckets = new Map();

        function isNearWhite(r, g, b) {
            return r > 235 && g > 235 && b > 235;
        }

        function isNearBlack(r, g, b) {
            return r < 20 && g < 20 && b < 20;
        }

        function rgbToHsl(r, g, b) {
            r /= 255; g /= 255; b /= 255;
            const max = Math.max(r,g,b), min = Math.min(r,g,b);
            let h, s, l = (max + min) / 2;

            if (max === min) {
                h = s = 0;
            } else {
                const d = max - min;
                s = l > 0.5 ? d / (2 - max - min) : d / (max + min);

                switch (max) {
                    case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                    case g: h = (b - r) / d + 2; break;
                    case b: h = (r - g) / d + 4; break;
                }

                h /= 6;
            }

            return { h, s, l };
        }

        for (let i = 0; i < pixels.length; i += 16) {
            let r = pixels[i];
            let g = pixels[i + 1];
            let b = pixels[i + 2];

            if (isNearWhite(r,g,b) || isNearBlack(r,g,b)) continue;

            // quantize
            r = Math.round(r / 20) * 20;
            g = Math.round(g / 20) * 20;
            b = Math.round(b / 20) * 20;

            const key = `${r},${g},${b}`;
            buckets.set(key, (buckets.get(key) || 0) + 1);
        }

        let bestColor = null;
        let bestScore = 0;

        for (const [key, count] of buckets.entries()) {
            const [r,g,b] = key.split(",").map(Number);
            const { s, l } = rgbToHsl(r,g,b);

            // Penalize very dark colors
            const lightnessWeight = l < 0.2 ? 0.4 : 1;

            // Prefer saturated colors
            const saturationWeight = s * 1.8;

            const score = count * (1 + saturationWeight) * lightnessWeight;

            if (score > bestScore) {
                bestScore = score;
                bestColor = key;
            }
        }

        if (bestColor) {
            return `rgb(${bestColor})`;
        }

        return "rgb(29,185,84)";
    }
    
    function isColorDark(rgbString) {
        const match = rgbString.match(/\d+/g);
        if (!match) return false;

        const [r, g, b] = match.map(Number);

        // standard luminance formula
        const luminance =
            (0.299 * r + 0.587 * g + 0.114 * b);

        return luminance < 120; // tweak threshold if needed
    }

    function ensureReadableColor(rgbString) {
        const match = rgbString.match(/\d+/g);
        if (!match) return rgbString;

        let [r, g, b] = match.map(Number);

        const luminance = (0.299 * r + 0.587 * g + 0.114 * b);

        if (luminance < 140) {
            // Lift toward white smoothly
            const liftAmount = 0.55;
            r = Math.min(255, Math.round(r + (255 - r) * liftAmount));
            g = Math.min(255, Math.round(g + (255 - g) * liftAmount));
            b = Math.min(255, Math.round(b + (255 - b) * liftAmount));
        }

        return `rgb(${r}, ${g}, ${b})`;
    }

    const loadPromises = treeData.map(item => {
        return new Promise(resolve => {
            const img = new Image();
            img.crossOrigin = "anonymous";
            img.src = item.image;

            img.onload = () => {
                imageCache.set(item.label, img);
                artistColorMap.set(item.label, extractDominantColor(img));
                resolve();
            };

            img.onerror = resolve;
        });
    });

    Promise.all(loadPromises).then(() => {

        // =========================
        // BAR CHART
        // =========================
        if (currentArtistChartType === "bar") {

            const labels = treeData.map(a => a.label);
            const values = treeData.map(a => a.value);

            const colors = labels.map(label =>
                artistColorMap.get(label) || "#1DB954"
            );

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
                        hoverBorderColor: "#1DB954",
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

                        const imgEl = imageCache.get(item.label);
                        const color = artistColorMap.get(item.label) || "#1DB954";

                        setActiveArtistFromItem(item, color, imgEl);
                    }
                }
            });

            setChartInstance(chart);

            if (treeData.length) {

                let target = treeData[0];

                if (currentActiveArtistLabel) {
                    const match = treeData.find(a => a.label === currentActiveArtistLabel);
                    if (match) target = match;
                }

                const imgEl = imageCache.get(target.label);
                const color = artistColorMap.get(target.label) || "#1DB954";

                setActiveArtistFromItem(target, color, imgEl);
            }

            const activeCard = document.querySelector(".ws-artist-active");
            if (activeCard) {
                requestAnimationFrame(() => {
                    activeCard.classList.remove("ws-fading");
                });
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
                        const raw = context?.raw;
                        const label =
                            raw?._data?.label ||
                            raw?.g ||
                            raw?.label;

                        return artistColorMap.get(label) || "#1DB954";
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
                    const raw = el?.$context?.raw || el?.$context?.raw?._data;

                    const label =
                        raw?._data?.label ||
                        raw?.g ||
                        raw?.label;

                    if (!label) return;

                    const item = treeData.find(t => t.label === label);
                    if (!item) return;

                    const imgEl = imageCache.get(label);
                    const color = artistColorMap.get(label) || "#1DB954";

                    setActiveArtistFromItem(item, color, imgEl);
                }
            }
        });

        setChartInstance(chart);
                
        if (treeData.length) {

            let target = treeData[0];

            if (currentActiveArtistLabel) {
                const match = treeData.find(a => a.label === currentActiveArtistLabel);
                if (match) target = match;
            }

            const imgEl = imageCache.get(target.label);
            const color = artistColorMap.get(target.label) || "#1DB954";

            setActiveArtistFromItem(target, color, imgEl);
        }
    });
}