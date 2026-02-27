export let metricCache = {};
export let workspaceBuildVersion = null;
export let wsChartInstance = null;

export let currentMetric =
    localStorage.getItem("wsCurrentMetric") || "avg-length";

export let currentSelection =
    localStorage.getItem("wsCurrentSelection") || "combined";

export function setMetricCache(cache) {
    metricCache = cache;
}

export function setWorkspaceBuildVersion(val) {
    workspaceBuildVersion = val;
}

export function setCurrentMetric(val) {
    currentMetric = val;
    localStorage.setItem("wsCurrentMetric", val);
}

export function setCurrentSelection(val) {
    currentSelection = val;
    localStorage.setItem("wsCurrentSelection", val);
}

export function setChartInstance(instance) {
    wsChartInstance = instance;
}

export function clearChartInstance() {
    if (wsChartInstance) {
        wsChartInstance.destroy();
        wsChartInstance = null;
    }
}