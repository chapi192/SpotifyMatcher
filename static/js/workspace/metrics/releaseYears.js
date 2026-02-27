import { clearChartInstance, setChartInstance } from "../state.js";

export function renderReleaseYears(data) {

    const out = document.getElementById("wsAnalyticsOutput");

    if (!data || !data.year_counts) {
        out.innerHTML = `<p style="opacity:0.7;">No release data.</p>`;
        clearChartInstance();
        return;
    }

    out.innerHTML = `
        <div style="margin-bottom:24px;">
            <div style="font-size:14px; opacity:0.6;">Release Span</div>
            <div style="font-size:42px; font-weight:700;">
                ${data.oldest_year}–${data.newest_year}
            </div>
            <div style="opacity:0.7;">
                Median ${data.median_year} • Span ${data.year_span} years
            </div>
        </div>

        <div style="position:relative; height:260px;">
            <canvas id="wsChart"></canvas>
        </div>
    `;

    clearChartInstance();

    const years = Object.keys(data.year_counts).map(Number).sort((a,b)=>a-b);
    const values = years.map(y => data.year_counts[y]);

    const ctx = document.getElementById("wsChart").getContext("2d");

    setChartInstance(new Chart(ctx, {
        type: "bar",
        data: { labels: years, datasets: [{ data: values }] },
        options: { plugins: { legend: { display: false } } }
    }));
}