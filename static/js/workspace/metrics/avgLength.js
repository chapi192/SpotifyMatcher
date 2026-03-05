import { renderHistogram } from "../charts.js";
import { formatTime, formatTotalRuntime, getConsistencyLabel, getTimeCommitmentLabel, getFlowDensityLabel, escapeHtml } from "../utils.js";
import { makeOverlayDraggable } from "../draggable.js";
import { wsChartInstance } from "../state.js";

export async function renderAvgLength(data, currentSelection) {

    const out = document.getElementById("wsAnalyticsOutput");

    if (wsChartInstance) {

        const chart = wsChartInstance;

        const currentMax = chart.scales.y.max;

        chart.options.scales.y.min = 0;
        chart.options.scales.y.max = currentMax;

        chart.update();

        // Animate bars down to zero
        chart.data.datasets.forEach(ds => {
            ds.data = ds.data.map(() => 0);
        });

        chart.update();

        await new Promise(resolve => setTimeout(resolve, 350));
    }

    const consistency = getConsistencyLabel(data.std_dev_seconds);
    const timeCommitmentLabel = getTimeCommitmentLabel(data.total_runtime_seconds);
    const flowLabel = getFlowDensityLabel(data.flow_density_pct);

    out.innerHTML = `
        <div class="ws-avg-full">

           <div class="ws-avg-header">

                <div class="ws-avg-title">
                    Average Track Length:
                    <span class="ws-avg-inline-number">
                        ${formatTime(data.average_length_seconds)}
                    </span>
                </div>

                <div class="ws-avg-selection">
                    ${
                        currentSelection === "combined"
                            ? `
                                <span class="ws-selection-name">All Selected</span>
                                <span class="ws-selection-meta">${data.track_count} tracks</span>
                            `
                            : `
                            <a 
                                href="https://open.spotify.com/playlist/${currentSelection}" 
                                target="_blank"
                                class="ws-selection-name ws-selection-link"
                            >
                                ${escapeHtml(data.playlist_name || "")}
                            </a>
                                <span class="ws-selection-meta">${data.track_count} tracks</span>
                            `
                    }
                </div>

            </div>

            <div class="ws-chart-overlay-wrap">
                <canvas id="wsChart"></canvas>

                <div class="ws-chart-overlay">

                    <span 
                        class="ws-panel-help ws-help"
                        data-tooltip=
                        "Commitment – total listening time of selection.\n
                    Flow Density – % of songs are near the average length.\n
                    Consistency – variability in duration.\n
                    Radio – % of tracks times within radio standards.
                    ">
                    ?
                    </span>

                    <div class="ws-overlay-row">
                        <span>Commitment</span>
                        <span>
                            ${timeCommitmentLabel}
                            (${formatTotalRuntime(data.total_runtime_seconds)})
                        </span>
                    </div>

                    <div class="ws-overlay-row">
                        <span>Flow Density</span>
                        <span>
                            ${flowLabel}
                            (${data.flow_density_pct}%)
                        </span>
                    </div>

                    <div class="ws-overlay-row">
                        <span>Consistency</span>
                        <span>${consistency.label}</span>
                    </div>

                    <div class="ws-overlay-row">
                        <span>
                            Radio
                        </span>
                        <span>${data.radio_pct}%</span>
                    </div>

                    <div class="ws-overlay-row">
                        <span>Median</span>
                        <span>${formatTime(data.median_length_seconds)}</span>
                    </div>

                    <div class="ws-overlay-row">
                        <span>Longest</span>
                        <div class="ws-overlay-value">
                            <a href="${data.longest_track.url}" target="_blank" class="ws-overlay-title">
                                ${escapeHtml(data.longest_track.name)}
                            </a>
                            <span class="ws-overlay-time">
                                (${formatTime(data.longest_track.seconds)})
                            </span>
                        </div>
                    </div>

                    <div class="ws-overlay-row">
                        <span>Shortest</span>
                        <div class="ws-overlay-value">
                            <a href="${data.shortest_track.url}" target="_blank" class="ws-overlay-title">
                                ${escapeHtml(data.shortest_track.name)}
                            </a>
                            <span class="ws-overlay-time">
                                (${formatTime(data.shortest_track.seconds)})
                            </span>
                        </div>
                    </div>

                </div>

        </div>
    `;

    renderHistogram(data.durations);

    makeOverlayDraggable(true);
}