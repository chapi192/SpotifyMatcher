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

    const padding = 16;

    const rect = tooltipEl.getBoundingClientRect();

    const help = document.querySelector(".ws-help:hover");

    let x;

    // Special case override
    if (help?.dataset.tooltipSide === "left") {
        x = e.clientX - rect.width - padding;
    } else {
        x = e.clientX + padding;
    }

    let y = e.clientY + padding;

    // Prevent overflow right
    if (x + rect.width > window.innerWidth) {
        x = e.clientX - rect.width - padding;
    }

    // Prevent overflow left
    if (x < 0) {
        x = e.clientX + padding;
    }

    // Prevent overflow bottom
    if (y + rect.height > window.innerHeight) {
        y = e.clientY - rect.height - padding;
    }

    tooltipEl.style.left = x + "px";
    tooltipEl.style.top = y + "px";
}