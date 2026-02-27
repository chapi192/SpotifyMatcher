export function escapeHtml(str) {
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
}

export function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function formatTotalRuntime(totalSeconds) {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    if (hours === 0) return `${minutes} min`;
    return `${hours}h ${minutes}m`;
}

export function getConsistencyLabel(stdDev) {
    if (stdDev < 30) return { label: "Tight" };
    if (stdDev < 60) return { label: "Balanced" };
    return { label: "Wide Range" };
}

export function getTimeCommitmentLabel(totalSeconds) {
    const hours = totalSeconds / 3600;
    if (hours < 1) return "Quick Session";
    if (hours < 2) return "Casual Listen";
    if (hours < 4) return "Extended Play";
    if (hours < 8) return "Work Day";
    if (hours < 16) return "Weekend Bop";
    if (hours < 100) return "Serious Investment";
    if (hours < 400) return "Epic Journey";
    return "Year-Long Listen";
}

export function getFlowDensityLabel(pct) {
    if (pct >= 60) return "Strong Flow";
    if (pct >= 40) return "Balanced Structure";
    return "Dynamic Structure";
}