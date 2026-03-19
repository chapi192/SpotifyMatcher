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

           <div class="ws-header">

                <div class="ws-title">
                    Average Track Length:
                    <span class="ws-title-number">
                        ${formatTime(data.average_length_seconds)}
                    </span>
                </div>

                <div class="ws-selection">
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
                        data-tooltip="This page analyzes the lengths of tracks in your selection.
                        
                        Commitment - The total time it would take to listen to all tracks in the selection, from a &quot;Quick Session&quot; (under 1 hour) to an &quot;Epic Journey&quot; (over 1000 hours).

                        Consistency - How grouped tracks are to the average length. &quot;Tight&quot; means tracks are close to the average, while &quot;Wide Range&quot; means there are many track lengths.

                        Radio - Percentage of tracks in radio-friendly length of 3 and 5 minutes.

                    "
                    >
                    Help
                    </span>

                    <div class="ws-overlay-row">
                        <span>Commitment</span>
                        <span>
                            ${timeCommitmentLabel}
                            (${formatTotalRuntime(data.total_runtime_seconds)})
                        </span>
                    </div>

                    <div class="ws-overlay-row">
                        <span>Consistency</span>
                        <span>
                            ${flowLabel}
                        </span>
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