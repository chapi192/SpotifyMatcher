import { fetchLibrary, fetchMetric } from "./api.js";
import { currentMetric, currentSelection, setCurrentSelection } from "./state.js";
import { renderAvgLength } from "./metrics/avgLength.js";
import { renderPopularity } from "./metrics/popularity.js";
import { renderArtistFrequency } from "./metrics/artistFrequency.js";
import { renderReleaseYears } from "./metrics/releaseYears.js";
import { renderPlaylistProfile } from "./metrics/playlistProfile.js";
import { renderGenres } from "./metrics/genres.js";
import { renderPlaylistSections, wireWorkspaceGlobals } from "./ui.js";
import { wsChartInstance, clearChartInstance } from "./state.js";
import { initTooltipSystem } from "./tooltip.js";
import { renderAlbumFrequency } from "./metrics/albums.js";
import { renderRelationships } from "./metrics/relationships.js";

async function loadWorkspace() {

    const selectionRes = await fetch("/api/selection");
    const selection = await selectionRes.json();

    const relBtn = document.getElementById("wsRelationshipsBtn");

    if (relBtn) {

        const multi = selection.selected_ids.length > 1;

        relBtn.style.display = multi ? "" : "none";

        // If we were previously in relationships but no longer valid
        if (!multi && currentMetric === "relationships") {

            const genresBtn = document.querySelector(
                '.ws-metric-btn[data-metric="genres"]'
            );

            setMetric("genres", genresBtn);
        }
    }

    if (selection.selected_ids.length === 0) {
        setCurrentSelection("combined");
    } else if (selection.selected_ids.length === 1) {
        setCurrentSelection(selection.selected_ids[0]);
    } else {
        setCurrentSelection("combined");
    }

    const data = await fetchLibrary();

    if (!data || data.status !== "ready") {
        document.getElementById("wsPlaylistSection").innerHTML = "<p>No playlists ready.</p>";
        return;
    }

    renderPlaylistSections(data);

    // Validate saved selection against current library
    const validPlaylistIds = data.playlists.map(p => p.playlist_id);

    if (currentSelection !== "combined" &&
        !validPlaylistIds.includes(currentSelection)) {

        if (data.playlist_count > 1) {
            setCurrentSelection("combined");
        } else if (data.playlist_count === 1 && data.playlists[0]) {
            setCurrentSelection(data.playlists[0].playlist_id);
        }
    }

    // NOW render playlist UI with corrected selection
    renderPlaylistSections(data);

    await maybeRenderAnalytics();

    // Sync active metric button visually
    document.querySelectorAll(".ws-metric-btn")
        .forEach(btn => {
            if (btn.dataset.metric === currentMetric) {
                btn.classList.add("active-metric");
            } else {
                btn.classList.remove("active-metric");
            }
        });

    const defaultBtn = document.querySelector(
        `.ws-metric-btn[data-metric="${currentMetric}"]`
    );

    if (defaultBtn) {
        setMetric(currentMetric, defaultBtn);
    }
}

async function animateOutCurrentMetric() {

    if (!wsChartInstance) return;

    const chart = wsChartInstance;

    // ===============================
    // CARTESIAN CHARTS (bar, line)
    // ===============================
    if (chart.scales?.y) {

        const currentMax = chart.scales.y.max;

        chart.options.scales.y.min = 0;
        chart.options.scales.y.max = currentMax;

        chart.update();

        chart.data.datasets.forEach(ds => {
            if (Array.isArray(ds.data)) {
                ds.data = ds.data.map(() => 0);
            }
        });

        chart.update();

        await new Promise(resolve => setTimeout(resolve, 300));
        clearChartInstance();
        return;
    }

    // ===============================
    // POLAR AREA
    // ===============================
    if (chart.config?.type === "polarArea") {

        const scale = chart.scales?.r;
        const currentMax = scale?.max;

        if (scale) {
            chart.options.scales.r.min = 0;
            chart.options.scales.r.max = currentMax;
            chart.update();
        }

        chart.data.datasets.forEach(ds => {
            ds.data = ds.data.map(() => 0);
        });

        chart.update();

        await new Promise(resolve => setTimeout(resolve, 300));
        clearChartInstance();
        return;
    }

    // ===============================
    // DOUGHNUT / PIE
    // ===============================
    if (chart.config?.type === "doughnut" ||
        chart.config?.type === "pie") {

        chart.data.datasets.forEach(ds => {
            ds.data = ds.data.map(() => 0);
        });

        chart.update();

        await new Promise(resolve => setTimeout(resolve, 300));
        clearChartInstance();
        return;
    }
}

async function maybeRenderAnalytics() {

    if (!currentMetric || !currentSelection) return;

    const payloadPromise = fetchMetric(currentMetric);
    await animateOutCurrentMetric();
    const payload = await payloadPromise;

    if (!payload || payload.status !== "ready") {
        document.getElementById("wsAnalyticsOutput").innerHTML =
            `<p style="opacity:0.7;">No data available.</p>`;
        return;
    }

    if (currentMetric === "relationships") {
        renderRelationships(payload.data);
        return;
    }

    const selectedData =
        currentSelection === "combined"
            ? payload.data.combined
            : payload.data.playlists[currentSelection];

    if (!selectedData) {
        document.getElementById("wsAnalyticsOutput").innerHTML =
            `<p style="opacity:0.7;">No profile available.</p>`;
        return;
    }

    if (currentMetric === "avg-length") {
        renderAvgLength(selectedData, currentSelection);
    } else if (currentMetric === "popularity") {
        renderPopularity(selectedData, currentSelection);
    } else if (currentMetric === "artist-frequency") {
        renderArtistFrequency(selectedData, currentSelection);
    } else if (currentMetric === "release-years") {
        renderReleaseYears(selectedData, currentSelection);
    } else if (currentMetric === "playlist-profile") {
        renderPlaylistProfile(selectedData, currentSelection);
    } else if (currentMetric === "genres") {
        renderGenres(selectedData, currentSelection);
    } else if (currentMetric === "album-frequency") {
        renderAlbumFrequency(selectedData, currentSelection);
    }
}

function highlightActiveMetric() {

    const buttons = document.querySelectorAll(".ws-metric-btn");

    buttons.forEach(btn => {

        const metric = btn.getAttribute("data-metric");

        if (metric === currentMetric) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }

    });

}

wireWorkspaceGlobals(maybeRenderAnalytics);
initTooltipSystem();
loadWorkspace();
highlightActiveMetric()