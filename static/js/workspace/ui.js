import { setCurrentSelection, setCurrentMetric, currentSelection } from "./state.js";

export function renderPlaylistSections(data) {
    const coverHtml = (imageUrl) => {
        if (imageUrl) {
            return `<div class="playlist-cover"><img src="${imageUrl}" alt="cover"></div>`;
        }
        return `<div class="no-cover">♪</div>`;
    };

    let cards = [];

    if (data.playlist_count > 1) {
        cards.push(`
            <div class="playlist-card no-animate ws-card-clickable ${
                currentSelection === "combined" ? "ws-active" : ""
            }"
            onclick="selectWorkspacePlaylist('combined', this)">
                ${coverHtml(null)}
                <div class="playlist-info">
                    <div class="playlist-name">All Selected</div>
                    <div class="playlist-count">
                        ${data.total_tracks} tracks • ${data.playlist_count} playlists
                    </div>
                </div>
            </div>
        `);
    }

    data.playlists.forEach(p => {
        cards.push(`
            <div class="playlist-card no-animate ws-card-clickable ${
                currentSelection === p.playlist_id ? "ws-active" : ""
            }"
            onclick="selectWorkspacePlaylist('${p.playlist_id}', this)">
                ${coverHtml(p.image)}
                <div class="playlist-info">
                    <div class="playlist-name">${escapeHtml(p.playlist_name)}</div>
                    <div class="playlist-count">${p.track_count} tracks</div>
                </div>
            </div>
        `);
    });

    document.getElementById("wsPlaylistSection").innerHTML = `
        <div class="playlist-grid ws-grid-tight">
            ${cards.join("")}
        </div>
    `;

    // If only one playlist, auto-select it
    if (data.playlist_count === 1 && data.playlists[0]) {
        setCurrentSelection(data.playlists[0].playlist_id);
        const firstCard = document.querySelector(".ws-card-clickable");
        if (firstCard) firstCard.classList.add("ws-active");
    }
}

export function wireWorkspaceGlobals(maybeRenderAnalytics) {
    // Metric buttons (inline onclick calls this)
    window.setMetric = (metric, element) => {
        setCurrentMetric(metric);

        document.querySelectorAll(".ws-metric-btn")
            .forEach(btn => btn.classList.remove("active-metric"));

        if (element) element.classList.add("active-metric");

        maybeRenderAnalytics();
    };

    window.selectWorkspacePlaylist = (pid, element) => {

        // 🚫 If already selected → do nothing
        if (element && element.classList.contains("ws-active")) {
            return;
        }

        setCurrentSelection(pid);

        document.querySelectorAll(".ws-card-clickable")
            .forEach(card => card.classList.remove("ws-active"));

        if (element) element.classList.add("ws-active");

        maybeRenderAnalytics();
    };
}

function escapeHtml(str) {
    return String(str)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}