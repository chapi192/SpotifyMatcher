import { metricCache } from "./state.js";

export async function fetchNavState() {
    const res = await fetch("/api/nav-state");
    return await res.json();
}

export async function fetchLibrary() {
    const res = await fetch("/api/library");
    return await res.json();
}

export async function fetchMetric(metric) {
    if (!metricCache[metric]) {
        const res = await fetch(`/api/${metric}`);
        metricCache[metric] = await res.json();
    }
    return metricCache[metric];
}