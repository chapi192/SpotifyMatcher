import { renderGenreChart } from "../charts.js";
import { escapeHtml } from "../utils.js";

export function renderPlaylistProfile(data) {

    const out = document.getElementById("wsAnalyticsOutput");

    if (!data) {
        out.innerHTML = `<p style="opacity:0.7;">No profile data.</p>`;
        return;
    }

    out.innerHTML = `
        <div style="margin-bottom:24px;">
            <div style="font-size:14px; opacity:0.6;">Playlist Identity</div>
            <div style="font-size:42px; font-weight:700;">
                ${escapeHtml(data.top_genre || "Mixed")}
            </div>
            <div style="opacity:0.7;">
                ${data.track_count} tracks • ${data.genre_spread} genres
            </div>
        </div>

        <div style="position:relative; height:260px;">
            <canvas id="wsChart"></canvas>
        </div>
    `;

    renderGenreChart(data.genre_counts);
}