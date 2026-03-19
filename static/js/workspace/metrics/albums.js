import { clearChartInstance, setChartInstance } from "../state.js";
import { escapeHtml } from "../utils.js";

let currentActiveAlbumLabel = null;

const albumImageCache = new Map();

function truncateText(str, maxLength = 34) {
    if (!str) return "";
    return str.length > maxLength
        ? str.slice(0, maxLength - 1) + "…"
        : str;
}

function hashToColor(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash % 360);
    return `hsl(${hue}, 60%, 45%)`;
}

function ensureReadableColor(rgbString) {
    const match = rgbString?.match?.(/\d+/g);
    if (!match) return rgbString;

    let [r, g, b] = match.map(Number);

    const luminance = (0.299 * r + 0.587 * g + 0.114 * b);

    if (luminance < 140) {
        const liftAmount = 0.55;
        r = Math.min(255, Math.round(r + (255 - r) * liftAmount));
        g = Math.min(255, Math.round(g + (255 - g) * liftAmount));
        b = Math.min(255, Math.round(b + (255 - b) * liftAmount));
    }

    return `rgb(${r}, ${g}, ${b})`;
}

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
        const max = Math.max(r, g, b), min = Math.min(r, g, b);
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

        if (isNearWhite(r, g, b) || isNearBlack(r, g, b)) continue;

        r = Math.round(r / 20) * 20;
        g = Math.round(g / 20) * 20;
        b = Math.round(b / 20) * 20;

        const key = `${r},${g},${b}`;
        buckets.set(key, (buckets.get(key) || 0) + 1);
    }

    let bestColor = null;
    let bestScore = 0;

    for (const [key, count] of buckets.entries()) {
        const [r, g, b] = key.split(",").map(Number);
        const { s, l } = rgbToHsl(r, g, b);

        const lightnessWeight = l < 0.2 ? 0.4 : 1;
        const saturationWeight = s * 1.8;

        const score = count * (1 + saturationWeight) * lightnessWeight;

        if (score > bestScore) {
            bestScore = score;
            bestColor = key;
        }
    }

    if (bestColor) return `rgb(${bestColor})`;
    return "rgb(29,185,84)";
}

export function renderAlbumFrequency(data, currentSelection) {
    const out = document.getElementById("wsAnalyticsOutput");

    if (!data || !data.top_10) {
        out.innerHTML = `<p style="opacity:0.7;">No album data.</p>`;
        clearChartInstance();
        return;
    }

    const missing = data.top_10.some(a => !albumImageCache.has(a.album_id));

    out.innerHTML = `
    <div class="ws-album-full">
        <div class="ws-header">
            <div class="ws-title">
                Album Diversity:
                <span class="ws-title-number">${data.diversity_score}</span>
            </div>

            <div class="ws-subrow">
                <div class="ws-selection">
                    ${
                        currentSelection === "combined"
                            ? `
                                <span class="ws-selection-name">All Selected</span>
                                <span class="ws-selection-meta">${data.track_count} tracks • ${data.unique_albums} albums</span>
                              `
                            : `
                                <a
                                    href="https://open.spotify.com/playlist/${currentSelection}"
                                    target="_blank"
                                    class="ws-selection-name ws-selection-link"
                                >
                                    ${escapeHtml(data.playlist_name || "")}
                                </a>
                                <span class="ws-selection-meta">${data.track_count} tracks • ${data.unique_albums} albums</span>
                              `
                    }
                </div>
            </div>
        </div>

        <div class="ws-album-layout">
            <div class="ws-album-panel">
                <div class="ws-artist-card">
                    <span
                        class="ws-panel-help ws-help"
                        data-tooltip="Album Concentration - How much the selection is dominated by a few albums.

Top Album - The album that contributes the most tracks.

Unique Appearances - % of albums that only appear once.

Avg Tracks / Album - Average number of tracks contributed by each album.

Top 10 Albums - % of tracks that come from the top 10 albums.

Multi-Track Albums - % of albums that contribute more than one track."
                    >?</span>

                    <div class="ws-album-label">Concentration</div>
                    <div class="ws-album-value">${data.concentration}</div>
                </div>

                <div class="ws-album-card">
                    <div class="ws-album-label">Top Album</div>
                    <div class="ws-album-value">
                        <a href="https://open.spotify.com/album/${data.top_album_id}" target="_blank">
                            ${truncateText(escapeHtml(data.top_album_name), 34)}
                        </a>
                        <span>(${data.dominance_pct}%)</span>
                    </div>
                </div>

                <div class="ws-album-card">
                    <div class="ws-album-label">Unique Appearances</div>
                    <div class="ws-album-value">${data.unique_appearance_pct}%</div>
                </div>

                <div class="ws-album-card">
                    <div class="ws-album-label">Avg Tracks / Album</div>
                    <div class="ws-album-value">${data.avg_tracks_per_album}</div>
                </div>

                <div class="ws-album-card">
                    <div class="ws-album-label">Top 10 Albums</div>
                    <div class="ws-album-value">${data.top10_album_share}%</div>
                </div>

                <div class="ws-album-card">
                    <div class="ws-album-label">Multi-Track Albums</div>
                    <div class="ws-album-value">${data.multi_album_pct}%</div>
                </div>
            </div>



            <div class="ws-album-right">
                <div class="ws-album-chart">
                    ${missing ? `
                    <div id="albumChartLoading" style="opacity:0.6; padding-top:120px; text-align:center;">
                        Fetching album covers...
                    </div>
                    ` : ``}
                    <canvas id="wsChart" style="display:none;"></canvas>
                </div>

                <div class="ws-album-active ws-album-card ws-fading" style="opacity:0;">
                    <div class="ws-album-active-row">
                        <div class="ws-album-active-img"></div>

                        <div class="ws-album-active-info">
                            <a class="ws-album-active-name" target="_blank"></a>
                            <div class="ws-album-active-meta"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    `;

    renderAlbumChart(data);
}

async function renderAlbumChart(data) {
    clearChartInstance();

    const canvas = document.getElementById("wsChart");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    const activeImg = document.querySelector(".ws-album-active-img");
    const activeName = document.querySelector(".ws-album-active-name");
    const activeMeta = document.querySelector(".ws-album-active-meta");

    function setActiveAlbumFromItem(item, color, imgEl) {
        if (!item || !activeImg || !activeName || !activeMeta) return;

        currentActiveAlbumLabel = item.label;
                
        activeImg.innerHTML = "";
        activeImg.style.minHeight = "64px";

        if (imgEl) {
            const url = imgEl.src;

            activeImg.style.opacity = "0";
            activeImg.style.backgroundImage = `url("${url}")`;
            activeImg.style.backgroundSize = "cover";
            activeImg.style.backgroundPosition = "center";
            activeImg.style.backgroundRepeat = "no-repeat";

            requestAnimationFrame(() => {
                activeImg.style.opacity = "1";
            });
        }

        activeName.textContent = item.label;
        activeName.href = `https://open.spotify.com/album/${item.album_id || ""}`;

        const trackCount = item.value || 0;
        const percent = data.track_count
            ? ((trackCount / data.track_count) * 100).toFixed(1)
            : 0;

        activeMeta.textContent =
            `Appears on ${trackCount} tracks • ${percent}% of selection`;

        const finalColor = ensureReadableColor(color || "rgb(29,185,84)");
        activeName.style.setProperty("--albumColor", finalColor);

        const card = document.querySelector(".ws-album-active");
        if (card) {
            requestAnimationFrame(() => card.classList.remove("ws-fading"));
        }
    }

    const pieData = (data.top_10 || []).map(a => ({
        label: a.album_name,
        value: a.count,
        album_id: a.album_id,
        image: albumImageCache.get(a.album_id) || null
    }));

    await fetchMissingAlbumCovers(data.top_10);

    if (!pieData.length) return;

    const albumColorMap = new Map();
    const imageCache = new Map();

        for (const item of pieData) {

            const url = albumImageCache.get(item.album_id);

            if (!url) {
                albumColorMap.set(item.label, hashToColor(item.label));
                continue;
            }

            const img = new Image();
            img.crossOrigin = "anonymous";
            img.src = url;

            await new Promise(resolve => {
                img.onload = resolve;
                img.onerror = resolve;
            });

            imageCache.set(item.label, img);
            albumColorMap.set(item.label, extractDominantColor(img));
        }

    const labels = pieData.map(a => a.label);
    const values = pieData.map(a => a.value);

    const colors = labels.map(label =>
        albumColorMap.get(label) || "rgb(29,185,84)"
    );

    const chart = new Chart(ctx, {
        type: "pie",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderWidth: 2,
                borderColor: "rgba(0,0,0,0.35)",
                hoverBorderWidth: 2,
                hoverBorderColor: "#1DB954",
                hoverOffset: 8
            }]
        },
        options: {
            maintainAspectRatio: false,
            layout: {
                padding: 20
            },
            animation: {
                duration: 400,
                easing: "easeOutCubic",
                onStart: () => {
                    const card = document.querySelector(".ws-album-active");
                    if (card) card.style.opacity = "1";
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            onHover: (event, activeEls) => {
                if (!activeEls?.length) return;

                const index = activeEls[0].index;
                const item = pieData[index];
                if (!item) return;

                const imgEl = imageCache.get(item.label);
                const color = albumColorMap.get(item.label) || "rgb(29,185,84)";

                setActiveAlbumFromItem(item, color, imgEl);
            }
        }
    });

    setChartInstance(chart);

    document.getElementById("albumChartLoading")?.remove();

    const canvasEl = document.getElementById("wsChart");
    if (canvasEl) canvasEl.style.display = "block";

    let target = pieData[0];

    if (currentActiveAlbumLabel) {
        const match = pieData.find(a => a.label === currentActiveAlbumLabel);
        if (match) target = match;
    }

    const imgEl = imageCache.get(target.label);
    const color = albumColorMap.get(target.label) || "rgb(29,185,84)";

    setActiveAlbumFromItem(target, color, imgEl);
}

async function fetchMissingAlbumCovers(albums) {

    const missing = albums
        .filter(a => !albumImageCache.has(a.album_id))
        .map(a => a.album_id);

    if (!missing.length) return;

    const res = await fetch("/api/album-images", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: missing })
    });

    const payload = await res.json();

    (payload.albums || []).forEach(a => {
        albumImageCache.set(a.album_id, a.image_url);
    });
}