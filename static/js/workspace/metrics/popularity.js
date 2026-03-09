/*
⚠️ DEPRECATED – February 2026 Spotify API Change

Spotify removed:
- track.popularity
- artist.popularity

This metric no longer reflects real Spotify data and should be
removed or redesigned in a future refactor.

Do NOT build new features on this file.
*/

import { renderPopularityHistogram } from "../charts.js";
import { escapeHtml } from "../utils.js";

function popTierCard(label, pct) {
    const safePct = (pct === undefined || pct === null)
        ? "—"
        : `${pct}%`;

    return `
        <div style="
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            padding: 12px;
            border-radius: 12px;
        ">
            <div style="opacity:0.75; font-size:13px;">
                ${label}
            </div>
            <div style="font-size:22px; font-weight:700; margin-top:4px;">
                ${safePct}
            </div>
        </div>
    `;
}

export function renderPopularity(data, currentSelection) {

    const out = document.getElementById("wsAnalyticsOutput");

    if (!data || !data.distribution || data.distribution.length === 0) {
        out.innerHTML = `<p style="opacity:0.7;">No popularity data.</p>`;
        return;
    }
    
    const tiers = data.tier_percentages || {};
    const most = data.most_popular_track;
    const least = data.least_popular_track;
    const toneClass = getPopularityToneClass(data.average_popularity);
    const avg = data.average_popularity;
    const median = data.median_popularity;
    const std = data.std_dev;

    const discoveryIndex = (100 - avg).toFixed(1);

    const skew =
        avg > median + 2 ? "Hit-Driven" :
        median > avg + 2 ? "Even" :
        "Low Impact";

    const identity =
        avg >= 70 ? "Mainstream" :
        avg >= 50 ? "Balanced" :
        avg >= 30 ? "Obscure" :
        "Underground";

    const breakout =
        most && most.popularity - median > 30
            ? "Contains a breakout hit"
            : "No extreme outliers";

    const radioCount = data.distribution.filter(p => p >= 60).length;

    const radioDensity = (
        radioCount / data.track_count * 100
    ).toFixed(1);

    out.innerHTML = `
    <div class="ws-pop-full ${toneClass}">

        <!-- HEADER -->
        <div class="ws-avg-header">

            <div class="ws-avg-title">
                Popularity Score:
                <span class="ws-avg-inline-number">
                    ${data.average_popularity}
                </span>
            </div>

            <div class="ws-avg-selection">
                ${
                    currentSelection === "combined"
                        ? `
                            <span class="ws-selection-name">
                                All Selected
                            </span>
                            <span class="ws-selection-meta">
                                ${data.track_count} tracks • ${data.playlist_count || "Multiple"} playlists
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
                                ${data.track_count} tracks
                            </span>
                        `
                }
            </div>

        </div>

        <!-- INSIGHT PANEL (FULL WIDTH) -->
        <div class="ws-pop-insights">

            <span 
                class="ws-panel-help ws-help"
                data-tooltip="Identity – overall popularity.\n
    Skew – how popularity affects your selection.\n
    Radio Density – % tracks above 60 popularity.
    ">
                ?
            </span>

            <div class="ws-pop-insight">
                <div class="ws-pop-insight-label">Identity</div>
                <div class="ws-pop-insight-value">${identity}</div>
            </div>

            <div class="ws-pop-insight">
                <div class="ws-pop-insight-label">Skew</div>
                <div class="ws-pop-insight-value">${skew}</div>
            </div>

            <div class="ws-pop-insight">
                <div class="ws-pop-insight-label">Radio Density</div>
                <div class="ws-pop-insight-value">${radioDensity}%</div>
            </div>

        </div>

        <!-- CHART CONTAINER BLOCK -->
        <div class="ws-pop-chart-wrap">

            <div class="ws-pop-chart-zone">

                <!-- Vertical Heat -->
                <div class="ws-pop-heat-vertical">

                    <div class="heat-label">POP.<br>SCORE</div>

                    <div class="heat-scale">
                        <span>100</span>
                        <span>75</span>
                        <span>50</span>
                        <span>25</span>
                        <span>0</span>
                    </div>

                    <div class="heat-track">
                        <div class="heat-fill"></div>
                    </div>

                </div>

                <!-- Histogram -->
                <div class="ws-chart-wrap" style="flex:1;">
                    <canvas id="wsChart"></canvas>
                </div>

            </div>

        </div>

    </div>
    `;

    const fill = out.querySelector(".heat-fill");

    if (fill) {
        fill.style.height = "0%";

        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                fill.style.height = `${data.average_popularity}%`;
            });
        });
    }

    renderPopularityHistogram(data.distribution);
}

function getPopularityToneClass(avg) {
    if (avg >= 70) return "pop-heat-high";
    if (avg >= 50) return "pop-heat-medium";
    return "pop-heat-low";
}