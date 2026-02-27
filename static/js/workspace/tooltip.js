let tooltipEl = null;

export function initTooltipSystem() {

    tooltipEl = document.createElement("div");
    tooltipEl.className = "ws-tooltip";
    document.body.appendChild(tooltipEl);

    document.addEventListener("mouseover", handleMouseOver);
    document.addEventListener("mouseout", handleMouseOut);
    document.addEventListener("mousemove", handleMouseMove);
}

function handleMouseOver(e) {
    const help = e.target.closest(".ws-help");
    if (!help) return;

    const text = help.dataset.tooltip;
    if (!text) return;

    tooltipEl.textContent = text;
    tooltipEl.classList.add("visible");
}

function handleMouseOut(e) {
    const help = e.target.closest(".ws-help");
    if (!help) return;

    tooltipEl.classList.remove("visible");
}

function handleMouseMove(e) {
    if (!tooltipEl.classList.contains("visible")) return;

    const padding = 14;

    const rect = tooltipEl.getBoundingClientRect();

    let x = e.clientX - rect.width - padding; // ← LEFT of cursor
    let y = e.clientY + padding;

    // If too far left, flip to right side
    if (x < 0) {
        x = e.clientX + padding;
    }

    // If too far down, move upward
    if (y + rect.height > window.innerHeight) {
        y = e.clientY - rect.height - padding;
    }

    tooltipEl.style.left = x + "px";
    tooltipEl.style.top = y + "px";
}