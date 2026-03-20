let currentChartType = "spiral";
let currentChart = null;
let landingArtistChart = null;
let currentPlaylistData = null;
let currentActiveArtistLabel = null;

function setActiveArtistFromItem(item, color, imgEl, totalTracks = 0) {

    const activeImg = document.querySelector(".landing-artist-active-img");
    const activeName = document.querySelector(".landing-artist-active-name");
    const activeMeta = document.querySelector(".landing-artist-active-meta");

    if (!item || !activeImg || !activeName || !activeMeta) return;

    currentActiveArtistLabel = item.label;

    activeImg.innerHTML = "";
    if (imgEl) {
        activeImg.appendChild(imgEl.cloneNode());
    } else {
        activeImg.innerHTML = `<div class="artist-placeholder"></div>`;
    }

    activeName.textContent = item.label;
    activeName.href = `https://open.spotify.com/artist/${item.artist_id || ""}`;

    const count = item.value || 0;
    const percent = totalTracks
        ? ((count / totalTracks) * 100).toFixed(1)
        : 0;

    activeMeta.textContent =
        `${count} tracks • ${percent}%`;

    activeName.style.setProperty("--artistColor", color || "#1DB954");
}

function getDecadeColor(index, total) {
    const t = index / Math.max(total - 1, 1);

    const r = Math.round(40);
    const g = Math.round(120 + t * 80);
    const b = Math.round(200 - t * 120);

    return `rgb(${r},${g},${b})`;
}

function formatBucketLabel(label, mode) {
    const year = Number(label);

    if (mode === "year") return `${year}`;
    if (mode === "decade") return `${year}s`;

    return label;
}

function getTimeGrouping(data) {
    const yearCounts = data.year_counts || {};
    const years = Object.keys(yearCounts);

    if (years.length <= 60) {
        return {
            mode: "year",
            labels: years
                .map(Number)
                .sort((a, b) => a - b)
                .map(String)
        };
    }

    return {
        mode: "decade",
        labels: Object.keys(data.decade_counts || {})
            .map(Number)
            .sort((a, b) => a - b)
            .map(String)
    };
}

function buildTimeSeries(data) {
    const grouping = getTimeGrouping(data);
    const labels = grouping.labels;

    const values =
        grouping.mode === "year"
            ? labels.map(y => data.year_counts?.[y] ?? 0)
            : labels.map(d => data.decade_counts?.[d] ?? 0);

    return {
        mode: grouping.mode,
        labels,
        values
    };
}

async function loadLandingArtists() {
    const res = await fetch("/api/landing-artists");
    const json = await res.json();

    console.log("LANDING ARTISTS:", json); // 👈 ADD THIS

    if (!json || json.status !== "ready") return;

    renderLandingArtistTreemap(json.data.combined);

    renderArtistPlaylists(
        Object.values(json.data.playlists)
    );
}

async function loadLandingRelationshipsLite() {
    const res = await fetch("/api/demo/relationships-lite");
    const json = await res.json();

    if (!json || json.status !== "ready") return;

    renderLandingRelationshipsLite(json.data);
}

async function initLanding() {
    const res = await fetch("/api/demo/release-years");
    const json = await res.json();

    if (json.status !== "ready") {
        console.error("No data");
        return;
    }

    const playlists = Object.values(json.data.playlists);

    const targetNames = [
        "Big Band / Swing",
        "60s Pop",
        "Electroswing",
        "Honky Tonk"
    ];

    const filtered = playlists.filter(p =>
        targetNames.includes(p.playlist_name)
    );

    renderPlaylistList(filtered);
    setupChartButtons();

    if (filtered.length) {
        const firstEl = document.querySelector(".playlist-card");
        selectPlaylist(filtered[0], firstEl);
    }
}

function renderPlaylistList(playlists) {
    const container = document.getElementById("playlistList");
    container.innerHTML = "";

    playlists.forEach(p => {
        const el = document.createElement("div");
        el.className = "playlist-card";

        el.innerHTML = `
            <img src="${p.image || ""}" alt="${p.playlist_name}">
            <div class="playlist-card-text">
                <span class="playlist-card-name">${p.playlist_name}</span>
                <span class="playlist-card-meta">${p.track_count} tracks</span>
            </div>
        `;

        el.onclick = () => selectPlaylist(p, el);

        container.appendChild(el);
    });
}

function selectPlaylist(playlist, el = null) {
    document.querySelectorAll(".playlist-card")
        .forEach(c => c.classList.remove("active"));

    if (el) {
        el.classList.add("active");
    }

    currentPlaylistData = playlist;
    updateHeader(playlist);
    renderChart(playlist);
}

function updateHeader(data) {

    document.getElementById("decadeTitle").textContent =
        data.playlist_name || "Playlist";

    document.getElementById("decadeSubtitle").textContent =
        `${data.track_count} tracks`;
}

function setupChartButtons() {
    document.querySelectorAll(".chart-btn").forEach(btn => {
        btn.onclick = () => {
            const type = btn.dataset.type;

            if (type === currentChartType) return;

            currentChartType = type;

            document.querySelectorAll(".chart-btn").forEach(b => {
                const isActive = b.dataset.type === type;
                b.classList.toggle("active", isActive);
                b.disabled = isActive;
            });

            if (currentPlaylistData) {
                renderChart(currentPlaylistData);
            }
        };
    });

    document.querySelectorAll(".chart-btn").forEach(btn => {
        const isActive = btn.dataset.type === currentChartType;
        btn.classList.toggle("active", isActive);
        btn.disabled = isActive;
    });
}

function renderChart(data) {
    if (currentChart) {
        currentChart.destroy();
        currentChart = null;
    }

    if (currentChartType === "spiral") {
        renderSpiralChart(data);
    } else {
        renderRingChart(data);
    }
}

function renderSpiralChart(data) {
    const canvas = document.getElementById("decadeChart");
    const ctx = canvas.getContext("2d");

    const { mode, labels, values } = buildTimeSeries(data);

    if (currentChart) {
        currentChart.destroy();
    }

    currentChart = new Chart(ctx, {
        type: "polarArea",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: labels.map((_, i) =>
                    getDecadeColor(i, labels.length)
                ),
                borderWidth: 1,
                borderColor: "rgba(0,0,0,0.3)",
                hoverBorderWidth: 2,
                hoverBorderColor: "#1DB954"
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 350,
                easing: "easeOutCubic"
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: items => {
                            const label = items[0].label;
                            return formatBucketLabel(label, mode);
                        },
                        label: item => `${item.raw} tracks`
                    }
                }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    ticks: { display: false },
                    grid: { color: "rgba(255,255,255,0.05)" },
                    angleLines: { color: "rgba(255,255,255,0.05)" }
                }
            }
        }
    });
}

function renderRingChart(data) {
    const canvas = document.getElementById("decadeChart");
    const ctx = canvas.getContext("2d");

    const { mode, labels, values } = buildTimeSeries(data);

    if (currentChart) {
        currentChart.destroy();
    }

    currentChart = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: labels.map((_, i) =>
                    getDecadeColor(i, labels.length)
                ),
                borderWidth: 2,
                borderColor: "rgba(0,0,0,0.35)",
                hoverBorderWidth: 2,
                hoverBorderColor: "#1DB954"
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "72%",
            radius: "88%",
            animation: {
                duration: 350,
                easing: "easeOutCubic"
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: items => {
                            const label = items[0].label;
                            return formatBucketLabel(label, mode);
                        },
                        label: item => `${item.raw} tracks`
                    }
                }
            }
        }
    });
}

function renderLandingArtistTreemap(artists) {

    const canvas = document.getElementById("landingRelationshipGraph");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    const treeData = (artists.top_10 || [])
        .map(a => ({
            label: a.artist_name,
            value: a.count,
            image: a.image_url,
            artist_id: a.artist_id
        }));

    if (!treeData.length) {
        console.warn("No valid artist data for treemap");
        return;
    }

    const artistColorMap = new Map();
    const imageCache = new Map();

    function extractDominantColor(img) {
        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d");

        const size = 50;
        canvas.width = size;
        canvas.height = size;

        ctx.drawImage(img, 0, 0, size, size);
        const pixels = ctx.getImageData(0, 0, size, size).data;

        const buckets = new Map();

        function isNearWhite(r, g, b) {
            return r > 235 && g > 235 && b > 235;
        }

        function isNearBlack(r, g, b) {
            return r < 20 && g < 20 && b < 20;
        }

        function rgbToHsl(r, g, b) {
            r /= 255; g /= 255; b /= 255;
            const max = Math.max(r,g,b), min = Math.min(r,g,b);
            let h, s, l = (max + min) / 2;

            if (max === min) {
                h = s = 0;
            } else {
                const d = max - min;
                s = l > 0.5 ? d / (2 - max - min) : d / (max + min);

                switch (max) {
                    case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                    case g: h = (b - r) / d + 2; break;
                    case b: h = (r - g) / d + 4; break;
                }

                h /= 6;
            }

            return { h, s, l };
        }

        for (let i = 0; i < pixels.length; i += 16) {
            let r = pixels[i];
            let g = pixels[i + 1];
            let b = pixels[i + 2];

            if (isNearWhite(r,g,b) || isNearBlack(r,g,b)) continue;

            r = Math.round(r / 20) * 20;
            g = Math.round(g / 20) * 20;
            b = Math.round(b / 20) * 20;

            const key = `${r},${g},${b}`;
            buckets.set(key, (buckets.get(key) || 0) + 1);
        }

        let bestColor = null;
        let bestScore = 0;

        for (const [key, count] of buckets.entries()) {
            const [r,g,b] = key.split(",").map(Number);
            const { s, l } = rgbToHsl(r,g,b);

            const lightnessWeight = l < 0.2 ? 0.4 : 1;
            const saturationWeight = s * 1.8;

            const score = count * (1 + saturationWeight) * lightnessWeight;

            if (score > bestScore) {
                bestScore = score;
                bestColor = key;
            }
        }

        if (bestColor) {
            return `rgb(${bestColor})`;
        }

        return "rgb(29,185,84)";
    }

    const loadPromises = treeData.map(item => {
        return new Promise(resolve => {
            const img = new Image();
            img.crossOrigin = "anonymous";
            if (!item.image) {
                resolve();
                return;
            }

            img.src = item.image;

            img.onload = () => {
                imageCache.set(item.label, img);
                artistColorMap.set(item.label, extractDominantColor(img));
                resolve();
            };

            img.onerror = resolve;
        });
    });

    Promise.all(loadPromises).then(() => {

        if (landingArtistChart) {
            landingArtistChart.destroy();
            landingArtistChart = null;
        }

        landingArtistChart = new Chart(ctx, {
            type: "treemap",
            data: {
                datasets: [{
                    tree: treeData,
                    key: "value",
                    groups: ["label"],
                    spacing: 3,
                    borderWidth: 2,
                    borderColor: "rgba(0,0,0,0.35)",
                    hoverBorderWidth: 2,
                    hoverBorderColor: "#1DB954",
                    backgroundColor(context) {
                        const raw = context?.raw;
                        const label =
                            raw?._data?.label ||
                            raw?.g ||
                            raw?.label;

                        return artistColorMap.get(label) || "#1DB954";
                    }
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 700,
                    easing: "easeOutCubic"
                },
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false }
                },

                onHover: (evt, activeEls) => {

                    if (!activeEls?.length) return;

                    const el = activeEls[0]?.element;
                    const raw = el?.$context?.raw || el?.$context?.raw?._data;

                    const label =
                        raw?._data?.label ||
                        raw?.g ||
                        raw?.label;

                    if (!label) return;

                    const item = treeData.find(t => t.label === label);
                    if (!item) return;

                    const imgEl = imageCache.get(label);
                    const color = artistColorMap.get(label) || "#1DB954";

                    const totalTracks = treeData.reduce((sum, a) => sum + a.value, 0);

                    setActiveArtistFromItem(item, color, imgEl, totalTracks);
                }
            }
        });

        if (treeData.length) {

            let target = treeData[0];

            if (currentActiveArtistLabel) {
                const match = treeData.find(a => a.label === currentActiveArtistLabel);
                if (match) target = match;
            }

            const imgEl = imageCache.get(target.label);
            const color = artistColorMap.get(target.label) || "#1DB954";

            const totalTracks = treeData.reduce((sum, a) => sum + a.value, 0);

            setActiveArtistFromItem(target, color, imgEl, totalTracks);
        }
    });
}

function renderArtistPlaylists(playlists) {

    const container = document.getElementById("artistPlaylistList");
    if (!container) return;

    container.innerHTML = "";

    const targetNames = [
        "Birth Of Rock",
        "I've Got To Drive Fast",
        "Opera",
        "Escape the Machine"
    ];

    const filtered = targetNames
        .map(name => playlists.find(p => p.playlist_name === name))
        .filter(Boolean);

    filtered.forEach(p => {

        const el = document.createElement("div");
        el.className = "playlist-card";

        el.innerHTML = `
            <img src="${p.image || ""}" alt="${p.playlist_name}">
            <div class="playlist-card-text">
                <span class="playlist-card-name">${p.playlist_name}</span>
                <span class="playlist-card-meta">${p.track_count || ""} tracks</span>
            </div>
        `;

        el.onclick = () => {

            document.querySelectorAll("#artistPlaylistList .playlist-card")
                .forEach(c => c.classList.remove("active"));

            el.classList.add("active");

            updateArtistHeader(p); 
            renderLandingArtistTreemap(p);
        };

        container.appendChild(el);
    });

    if (filtered.length) {
        const first = container.querySelector(".playlist-card");
        first?.click();
    }
}

function updateArtistHeader(data) {

    const titleEl = document.getElementById("artistTitle");
    const subtitleEl = document.getElementById("artistSubtitle");

    if (!titleEl || !subtitleEl) return;

    titleEl.textContent =
        data.playlist_name || "Playlist";

    subtitleEl.textContent =
        `${data.track_count || 0} tracks`;
}

function renderLandingRelationshipsLite(data) {

    let hoveredNode = null;
    let hoveredEdge = null;
    let visibleEdges = [];

    const weights = {
        genre: 0.45,
        artist: 0.85,
        decade: 0.40
    };

    const container = document.getElementById("landingRelationshipWrap");
    if (!container) return;

    container.innerHTML = `
        <div class="landing-rel-canvas-wrap">
            <canvas id="landingRelationshipCanvas"></canvas>
        </div>
    `;

    const canvas = document.getElementById("landingRelationshipCanvas");
    const wrap = canvas.parentElement;
    const ctx = canvas.getContext("2d");

    const dpr = window.devicePixelRatio || 1;

    const rect = wrap.getBoundingClientRect();

    const width = rect.width;
    const height = rect.height || 700;

    canvas.width = width * dpr;
    canvas.height = height * dpr;

    canvas.style.width = width + "px";
    canvas.style.height = height + "px";

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    preloadImages(data.playlists).then(images => {

        const nodes = data.playlists.map((p, i) => ({
            ...p,
            x: 0,
            y: 0,
            vx: 0,
            vy: 0,
            img: images[i]
        }));

        startGraph(nodes);
    });

    function startGraph(nodes) {
        const nodeMap = new Map(nodes.map(n => [n.playlist_id, n]));
        const edges = data.edges.map(e => ({ ...e }));

        function recompute() {
            edges.forEach(e => {
                e.score =
                    weights.genre * e.genre_score +
                    weights.artist * e.artist_score +
                    weights.decade * e.decade_score;
            });
        }

        function clamp(v, min, max) {
            return Math.max(min, Math.min(max, v));
        }

        function initialize() {
            const cx = width / 2;
            const cy = height / 2;
            const r = Math.min(width, height) * 0.38;

            nodes.forEach((n, i) => {
                const angle = (i / nodes.length) * Math.PI * 2;
                n.x = cx + Math.cos(angle) * r + (Math.random() - 0.5) * 120;
                n.y = cy + Math.sin(angle) * r + (Math.random() - 0.5) * 120;
            });
        }

        function runLayout() {
            for (let step = 0; step < 250; step++) {

                for (let i = 0; i < nodes.length; i++) {
                    const a = nodes[i];

                    for (let j = i + 1; j < nodes.length; j++) {
                        const b = nodes[j];

                        let dx = b.x - a.x;
                        let dy = b.y - a.y;

                        let distSq = dx * dx + dy * dy || 0.01;
                        const force = 9000 / distSq;
                        const dist = Math.sqrt(distSq);

                        dx /= dist;
                        dy /= dist;

                        a.vx -= dx * force * 0.01;
                        a.vy -= dy * force * 0.01;
                        b.vx += dx * force * 0.01;
                        b.vy += dy * force * 0.01;
                    }
                }
            }
        }

        function stepLayout() {

            for (let i = 0; i < nodes.length; i++) {
                const a = nodes[i];

                for (let j = i + 1; j < nodes.length; j++) {
                    const b = nodes[j];

                    let dx = b.x - a.x;
                    let dy = b.y - a.y;

                    let distSq = dx * dx + dy * dy || 0.01;
                    const force = 12000 / distSq;
                    const dist = Math.sqrt(distSq);

                    dx /= dist;
                    dy /= dist;

                    a.vx -= dx * force * 0.002;
                    a.vy -= dy * force * 0.002;
                    b.vx += dx * force * 0.002;
                    b.vy += dy * force * 0.002;
                }
            }

            visibleEdges.forEach(e => {
                const a = nodeMap.get(e.source);
                const b = nodeMap.get(e.target);

                if (!a || !b) return;

                let dx = b.x - a.x;
                let dy = b.y - a.y;

                let dist = Math.sqrt(dx * dx + dy * dy) || 1;

                dx /= dist;
                dy /= dist;

                const pull = e.score * 0.01;

                a.vx += dx * pull;
                a.vy += dy * pull;
                b.vx -= dx * pull;
                b.vy -= dy * pull;
            });

            nodes.forEach(n => {
                n.vx *= 0.92;
                n.vy *= 0.92;

                n.x += n.vx;
                n.y += n.vy;
            });
        }

        function buildVisibleEdges() {
            const edgesByNode = new Map();

            edges.forEach(e => {
                if (e.score <= 0.01) return;

                if (!edgesByNode.has(e.source)) edgesByNode.set(e.source, []);
                if (!edgesByNode.has(e.target)) edgesByNode.set(e.target, []);

                edgesByNode.get(e.source).push(e);
                edgesByNode.get(e.target).push(e);
            });

            const kept = new Set();

            edgesByNode.forEach(list => {
                list
                    .sort((a, b) => b.score - a.score)
                    .slice(0, 3)
                    .forEach(e => kept.add(e));
            });

            visibleEdges = [...kept];
        }

        function draw() {

            ctx.save();
            ctx.setTransform(1, 0, 0, 1, 0, 0);
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.restore();

            // EDGES
            visibleEdges.forEach(e => {

                if (e.score <= 0.01) return;

                const a = nodeMap.get(e.source);
                const b = nodeMap.get(e.target);
                if (!a || !b) return;

                ctx.beginPath();
                ctx.moveTo(a.x, a.y);
                ctx.lineTo(b.x, b.y);

                let alpha = 0.15 + e.score * 0.5;
                let width = 1 + e.score * 3;

                if (hoveredEdge === e) {
                    alpha = 1;
                    width += 2;
                }

                if (
                    hoveredNode &&
                    (e.source === hoveredNode.playlist_id || e.target === hoveredNode.playlist_id)
                ) {
                    alpha = 0.9;
                    width += 1.5;
                }

                ctx.strokeStyle = `rgba(29,185,84,${alpha})`;

                ctx.lineWidth = width;

                ctx.stroke();
            });

            // NODES
            nodes.forEach(n => {

                const isHovered = hoveredNode === n;

                const r = isHovered ? 42 : 36;

                ctx.save();

                ctx.beginPath();
                ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
                ctx.closePath();
                ctx.clip();

                if (n.img && n.img.complete) {
                    const size = Math.min(n.img.width, n.img.height);

                    ctx.drawImage(
                        n.img,
                        (n.img.width - size) / 2,
                        (n.img.height - size) / 2,
                        size,
                        size,
                        n.x - r,
                        n.y - r,
                        r * 2,
                        r * 2
                    );
                } else {
                    ctx.fillStyle = "rgba(12,18,30,0.95)";
                    ctx.fill();
                }

                ctx.restore();

                // border
                ctx.beginPath();
                ctx.arc(n.x, n.y, r, 0, Math.PI * 2);

                ctx.strokeStyle = isHovered
                    ? "rgba(29,185,84,1)"
                    : "rgba(255,255,255,0.08)";

                ctx.lineWidth = isHovered ? 2.5 : 1.5;
                ctx.stroke();
            });
        }

        function distanceToSegment(px, py, x1, y1, x2, y2) {
            const dx = x2 - x1;
            const dy = y2 - y1;

            const t = Math.max(0, Math.min(1,
                ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
            ));

            const sx = x1 + t * dx;
            const sy = y1 + t * dy;

            return Math.hypot(px - sx, py - sy);
        }

        function recenterGraph() {

            let minX = Infinity, maxX = -Infinity;
            let minY = Infinity, maxY = -Infinity;

            nodes.forEach(n => {
                minX = Math.min(minX, n.x);
                maxX = Math.max(maxX, n.x);
                minY = Math.min(minY, n.y);
                maxY = Math.max(maxY, n.y);
            });

            let sumX = 0, sumY = 0;

            nodes.forEach(n => {
                sumX += n.x;
                sumY += n.y;
            });

            const graphCenterX = sumX / nodes.length;
            const graphCenterY = sumY / nodes.length;

            const targetX = width / 2;
            const targetY = height / 2;

            const dx = targetX - graphCenterX;
            const dy = targetY - graphCenterY;

            nodes.forEach(n => {
                n.x += dx;
                n.y += dy;
            });
        }

        canvas.addEventListener("mousemove", e => {

            const rect = canvas.getBoundingClientRect();

            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            hoveredNode = null;
            hoveredEdge = null;

            for (const n of nodes) {
                const dist = Math.hypot(mx - n.x, my - n.y);

                const baseRadius = 36;

                if (dist < baseRadius) {
                    hoveredNode = n;
                    break;
                }
            }

            if (!hoveredNode) {
                for (const e of visibleEdges) {
                    const a = nodeMap.get(e.source);
                    const b = nodeMap.get(e.target);

                    if (!a || !b) continue;

                    const dist = distanceToSegment(mx, my, a.x, a.y, b.x, b.y);
                    if (dist < 10) {
                        hoveredEdge = e;
                        break;
                    }
                }
            }

            draw();
        });

        recompute();
        buildVisibleEdges();
        initialize();
        runLayout();

        for (let i = 0; i < 40; i++) {
            stepLayout();
        }
        recenterGraph();

        buildVisibleEdges();
        draw();
    }
}

function preloadImages(playlists) {
    return Promise.all(
        playlists.map(p => {
            return new Promise(resolve => {
                const img = new Image();
                img.crossOrigin = "anonymous";

                if (!p.image) {
                    resolve(null);
                    return;
                }

                img.src = p.image;

                img.onload = () => resolve(img);
                img.onerror = () => resolve(null);
            });
        })
    );
}

initLanding();
loadLandingArtists();
loadLandingRelationshipsLite();