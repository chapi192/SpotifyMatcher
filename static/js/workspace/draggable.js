export function makeOverlayDraggable(initial = false) {

    const overlay = document.querySelector(".ws-chart-overlay");
    const container =
        document.querySelector(".ws-avg-full") ||
        document.querySelector(".ws-pop-full");

    if (!overlay || !container) return;

    let isDragging = false;
    let offsetX = 0;
    let offsetY = 0;

    const STORAGE_KEY = "wsOverlayPosition";

    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
        const { left, top } = JSON.parse(saved);

        overlay.style.right = "auto";
        overlay.style.left = left + "px";
        overlay.style.top = top + "px";
    }

    overlay.addEventListener("mousedown", (e) => {
        isDragging = true;
        overlay.classList.add("dragging");

        const rect = overlay.getBoundingClientRect();
        offsetX = e.clientX - rect.left;
        offsetY = e.clientY - rect.top;
    });

    document.addEventListener("mousemove", (e) => {
        if (!isDragging) return;

        const containerRect = container.getBoundingClientRect();

        let newLeft = e.clientX - containerRect.left - offsetX;
        let newTop = e.clientY - containerRect.top - offsetY;

        const maxLeft = containerRect.width - overlay.offsetWidth;
        const maxTop = containerRect.height - overlay.offsetHeight;

        newLeft = Math.max(0, Math.min(newLeft, maxLeft));
        newTop = Math.max(0, Math.min(newTop, maxTop));

        overlay.style.left = newLeft + "px";
        overlay.style.top = newTop + "px";
        overlay.style.right = "auto";

        localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify({ left: newLeft, top: newTop })
        );
    });

    document.addEventListener("mouseup", () => {
        isDragging = false;
        overlay.classList.remove("dragging");
    });
}