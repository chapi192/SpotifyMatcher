import { clearChartInstance, setChartInstance } from "../state.js";
import { escapeHtml } from "../utils.js";
import { wsChartInstance } from "../state.js";

let currentArtistChartType = "bar";

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
                            ${escapeHtml(data.max_artist_track_name)}
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

        activeImg.innerHTML = "";
        if (imgEl) activeImg.appendChild(imgEl.cloneNode());

        activeName.textContent = item.label;
        activeName.href = `https://open.spotify.com/artist/${item.artist_id || ""}`;
                
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
        const c = document.createElement("canvas");
        const cx = c.getContext("2d");

        c.width = 40;
        c.height = 40;

        cx.drawImage(img, 0, 0, 40, 40);
        const pixels = cx.getImageData(0, 0, 40, 40).data;

        let r = 0, g = 0, b = 0, count = 0;

        for (let i = 0; i < pixels.length; i += 16) {
            r += pixels[i];
            g += pixels[i + 1];
            b += pixels[i + 2];
            count++;
        }

        r = Math.round(r / count);
        g = Math.round(g / count);
        b = Math.round(b / count);

        return `rgb(${r}, ${g}, ${b})`;
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
                        borderRadius: 4
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

            // default active = top artist
            if (treeData.length) {
                const first = treeData[0];
                const imgEl = imageCache.get(first.label);
                const color = artistColorMap.get(first.label) || "#1DB954";
                setActiveArtistFromItem(first, color, imgEl);
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
            const first = treeData[0];
            const imgEl = imageCache.get(first.label);
            const color = artistColorMap.get(first.label) || "#1DB954";
            setActiveArtistFromItem(first, color, imgEl);
        }
    });
}