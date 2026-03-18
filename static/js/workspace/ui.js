import { setCurrentSelection, setCurrentMetric, currentSelection } from "./state.js";

export function renderPlaylistSections(data) {

    const container = document.querySelector(".ws-sidebar-list");

    const coverHtml = (imageUrl) => {
        if (imageUrl) {
            return `<div class="ws-sidebar-cover"><img src="${imageUrl}" alt=""></div>`;
        }
        return `<div class="ws-sidebar-cover">♪</div>`;
    };

    let items = [];

    // Combined option
    if (data.playlist_count > 1) {

        items.push(`
            <div class="ws-sidebar-item ${
                currentSelection === "combined" ? "active" : ""
            }"
            onclick="selectWorkspacePlaylist('combined', this)">

                ${coverHtml(null)}

                <div class="ws-sidebar-info">
                    <div class="ws-sidebar-name">All Selected</div>
                    <div class="ws-sidebar-count">
                        ${data.total_tracks} tracks • ${data.playlist_count} playlists
                    </div>
                </div>

            </div>
        `);

    }

    // Individual playlists
    data.playlists.forEach(p => {

        items.push(`
            <div class="ws-sidebar-item ${
                currentSelection === p.playlist_id ? "active" : ""
            }"
            onclick="selectWorkspacePlaylist('${p.playlist_id}', this)">

                ${coverHtml(p.image)}

                <div class="ws-sidebar-info">
                    <div class="ws-sidebar-name">${escapeHtml(p.playlist_name)}</div>
                    <div class="ws-sidebar-count">${p.track_count} tracks</div>
                </div>

            </div>
        `);

    });

    container.innerHTML = items.join("");

    // Auto select if only one playlist
    if (data.playlist_count === 1 && data.playlists[0]) {

        setCurrentSelection(data.playlists[0].playlist_id);

        const first = document.querySelector(".ws-sidebar-item");

        if (first) first.classList.add("active");

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
        if (element && element.classList.contains("active")) {
            return;
        }

        setCurrentSelection(pid);

        document.querySelectorAll(".ws-sidebar-item")
            .forEach(card => card.classList.remove("active"));

        if (element) element.classList.add("active");

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