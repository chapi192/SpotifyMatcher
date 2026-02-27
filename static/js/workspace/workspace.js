import { fetchLibrary, fetchMetric } from "./api.js";
import { currentMetric, currentSelection, setCurrentSelection } from "./state.js";
import { renderAvgLength } from "./metrics/avgLength.js";
import { renderPopularity } from "./metrics/popularity.js";
import { renderArtistFrequency } from "./metrics/artistFrequency.js";
import { renderReleaseYears } from "./metrics/releaseYears.js";
import { renderPlaylistProfile } from "./metrics/playlistProfile.js";
import { renderPlaylistSections, wireWorkspaceGlobals } from "./ui.js";
import { wsChartInstance } from "./state.js";
import { initTooltipSystem } from "./tooltip.js";

async function loadWorkspace() {
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
}

async function animateOutCurrentMetric() {

    const output = document.getElementById("wsAnalyticsOutput");

    const animations = [];

    if (wsChartInstance) {

        if (wsChartInstance.config.type === "treemap") {
            const chartWrap = document.querySelector(".ws-artist-chart");

            if (chartWrap) {
                chartWrap.classList.add("ws-shrinking");

                animations.push(
                    new Promise(resolve => setTimeout(resolve, 180))
                );
            }

            await Promise.all(animations);
            return;
        }

        const chart = wsChartInstance;

        const currentMax = chart.scales.y.max;

        // Lock axis range
        chart.options.scales.y.min = 0;
        chart.options.scales.y.max = currentMax;

        chart.update();

        // Now shrink bars
        chart.data.datasets.forEach(ds => {
            ds.data = ds.data.map(() => 0);
        });

        chart.update();

        animations.push(
            new Promise(resolve => setTimeout(resolve, 350))
        );
    }

    const activeCard = output.querySelector(".ws-artist-active");
    if (activeCard) {
        activeCard.classList.add("ws-fading");

        animations.push(
            new Promise(resolve => setTimeout(resolve, 180))
        );
    }

    // --- Heat bar shrink ---
    const heatFill = output.querySelector(".heat-fill");

    if (heatFill) {
        heatFill.style.height = "0%";

        animations.push(
            new Promise(resolve => setTimeout(resolve, 350))
        );
    }

    // Wait for both simultaneously
    await Promise.all(animations);
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
        renderReleaseYears(selectedData);
    } else if (currentMetric === "playlist-profile") {
        renderPlaylistProfile(selectedData);
    }
}

wireWorkspaceGlobals(maybeRenderAnalytics);
initTooltipSystem();
loadWorkspace();