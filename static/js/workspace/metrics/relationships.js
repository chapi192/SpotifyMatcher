import { escapeHtml } from "../utils.js";
import { setCurrentSelection } from "../state.js";

let relationshipAnimId = null;
let relationshipCleanup = null;

let zoom = 1;
let targetZoom = 1;
let panX = 0;
let panY = 0;
let mouseX = 0;
let mouseY = 0;

let dragging = false;
let dragStartX = 0;
let dragStartY = 0;

let selectedNodeId = null;
let selectedEdgeKey = null;
let strongestEdgeGlobal = null;

let relationshipGraphState = {
    signature: "",
    positions: new Map(),
    zoom: 1,
    targetZoom: 1,
    panX: 0,
    panY: 0
};

let weights = {
    genre: 35,
    artist: 25,
    album: 10,
    decade: 5,
    track: 15,
    duration: 10
};

let lockedWeights = {
    genre: false,
    artist: false,
    album: false,
    decade: false,
    track: false,
    duration: false
};

function recomputeScores(edges, scoreEl, weightEls) {

    const total =
        weights.genre +
        weights.artist +
        weights.album +
        weights.decade +
        weights.track +
        weights.duration;

    if (total <= 0) {
        weights.genre = 100;
        weights.artist = 0;
        weights.album = 0;
        weights.decade = 0;
        weights.track = 0;
        weights.duration = 0;
    }

    const safeTotal =
        weights.genre +
        weights.artist +
        weights.album +
        weights.decade +
        weights.track +
        weights.duration;

    const g = weights.genre / safeTotal;
    const a = weights.artist / safeTotal;
    const al = weights.album / safeTotal;
    const d = weights.decade / safeTotal;
    const t = weights.track / safeTotal;
    const dur = weights.duration / safeTotal;

    let scoreSum = 0;

    edges.forEach(e => {

        const newScore =
            g * e.genre_score +
            a * e.artist_score +
            al * e.album_score +
            d * e.decade_score +
            t * e.track_score +
            dur * e.duration_score;

        e.score = newScore <= 0.0001 ? 0 : newScore;

        if (e.score > 0) {
            scoreSum += e.score;
        }

    });

    if (scoreEl) {
        const avg = edges.length ? scoreSum / edges.length : 0;
        scoreEl.textContent = `${(avg * 100).toFixed(1)}%`;
    }

    if (weightEls) {
        weightEls.genre.textContent = `${Math.round(g * 100)}%`;
        weightEls.artist.textContent = `${Math.round(a * 100)}%`;
        weightEls.album.textContent = `${Math.round(al * 100)}%`;
        weightEls.decade.textContent = `${Math.round(d * 100)}%`;
        weightEls.track.textContent = `${Math.round(t * 100)}%`;
        weightEls.duration.textContent = `${Math.round(dur * 100)}%`;
    }
}

function applySliderValue(changedKey, rawValue) {

    if (lockedWeights[changedKey]) return;

    const keys = Object.keys(weights);

    const lockedTotal = keys
        .filter(k => lockedWeights[k])
        .reduce((sum,k)=>sum+weights[k],0);

    const unlockedKeys = keys.filter(k => !lockedWeights[k]);

    const remaining = 100 - lockedTotal;

    if (remaining <= 0) return;

    const newValue = clamp(rawValue, 0, remaining);
    weights[changedKey] = newValue;

    const otherKeys = unlockedKeys.filter(k => k !== changedKey);

    const available = remaining - newValue;

    if (otherKeys.length === 0) return;

    const othersTotal = otherKeys.reduce((s,k)=>s+weights[k],0);

    if (othersTotal <= 0) {

        const share = available / otherKeys.length;

        otherKeys.forEach(k => {
            weights[k] = clamp(share,0,100);
        });

    } else {

        otherKeys.forEach(k => {
            const v = (weights[k] / othersTotal) * available;
            weights[k] = clamp(v,0,100);
        });

    }
}

function syncSlidersFromWeights(sliders, weightEls) {

    Object.entries(sliders).forEach(([key, slider]) => {
        slider.value = clamp(Math.round(weights[key]), 0, 100);
    });

    const total =
        weights.genre +
        weights.artist +
        weights.album +
        weights.decade +
        weights.track +
        weights.duration;

    const safeTotal = total || 1;

    weightEls.genre.textContent = `${Math.round(weights.genre / safeTotal * 100)}%`;
    weightEls.artist.textContent = `${Math.round(weights.artist / safeTotal * 100)}%`;
    weightEls.album.textContent = `${Math.round(weights.album / safeTotal * 100)}%`;
    weightEls.decade.textContent = `${Math.round(weights.decade / safeTotal * 100)}%`;
    weightEls.track.textContent = `${Math.round(weights.track / safeTotal * 100)}%`;
    weightEls.duration.textContent = `${Math.round(weights.duration / safeTotal * 100)}%`;
}

function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

function getEdgeKey(edge) {
    const a = String(edge.source);
    const b = String(edge.target);
    return a < b ? `${a}__${b}` : `${b}__${a}`;
}

function updateStrongestEdge(edges) {

    strongestEdgeGlobal = null;

    for (const e of edges) {
        if (e.score <= 0) continue;

        if (!strongestEdgeGlobal || e.score > strongestEdgeGlobal.score) {
            strongestEdgeGlobal = e;
        }
    }
}

function getGraphSignature(playlists) {
    return playlists
        .map(p => String(p.playlist_id))
        .sort()
        .join("|");
}

function saveGraphState(nodes) {
    relationshipGraphState.positions = new Map(
        nodes.map(node => [
            node.playlist_id,
            { x: node.x, y: node.y }
        ])
    );

    relationshipGraphState.zoom = zoom;
    relationshipGraphState.targetZoom = targetZoom;
    relationshipGraphState.panX = panX;
    relationshipGraphState.panY = panY;
}

function restoreGraphState(nodes) {
    let restoredCount = 0;

    nodes.forEach(node => {
        const saved = relationshipGraphState.positions.get(node.playlist_id);
        if (!saved) return;

        node.x = saved.x;
        node.y = saved.y;
        node.vx = 0;
        node.vy = 0;
        restoredCount++;
    });

    if (restoredCount > 0) {
        zoom = relationshipGraphState.zoom;
        targetZoom = relationshipGraphState.targetZoom;
        panX = relationshipGraphState.panX;
        panY = relationshipGraphState.panY;
        return true;
    }

    return false;
}

function getPositiveEdges(edges) {
    return edges.filter(e => e.score > 0);
}

function scoreToLabel(score) {
    if (score >= 0.75) return "Very Close";
    if (score >= 0.55) return "Strong Overlap";
    if (score >= 0.35) return "Moderate Overlap";
    if (score >= 0.18) return "Loose Connection";
    return "Distant";
}

function scoreToStroke(score) {
    const alpha = 0.4 + score * 0.55;
    return `rgba(29,185,84,${alpha.toFixed(3)})`;
}

function scoreToGlow(score) {
    return 8 + score * 18;
}

function scoreToWidth(score) {
    return 1 + score * 4.5;
}

function scoreToRadius(score) {
    return 34 + score * 16;
}

function buildNodeMap(playlists) {

    const map = new Map();

    playlists.forEach((p, index) => {

        const img = new Image();
        img.crossOrigin = "anonymous";

        if (p.image) {
            img.src = p.image;
        }

        map.set(p.playlist_id, {
            ...p,
            x: 0,
            y: 0,
            vx: 0,
            vy: 0,
            fx: 0,
            fy: 0,
            index,
            img
        });

    });

    return map;
}

function initializeNodePositions(nodes, width, height) {
    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.min(width, height) * 0.28;
    const count = nodes.length;

    nodes.forEach((node, i) => {
        const angle = (Math.PI * 2 * i) / Math.max(count, 1);
        node.x = cx + Math.cos(angle) * radius;
        node.y = cy + Math.sin(angle) * radius;
        node.vx = 0;
        node.vy = 0;
    });
}

function runLayout(nodes, edges, width, height) {
    if (!nodes.length) return;

    const nodeById = new Map(nodes.map(n => [n.playlist_id, n]));
    const cx = width / 2;
    const cy = height / 2;

    for (let step = 0; step < 220; step++) {

        for (let i = 0; i < nodes.length; i++) {
            const a = nodes[i];

            for (let j = i + 1; j < nodes.length; j++) {
                const b = nodes[j];

                let dx = b.x - a.x;
                let dy = b.y - a.y;
                let distSq = dx * dx + dy * dy;

                if (distSq < 0.01) distSq = 0.01;

                const force = 32000 / distSq;
                const dist = Math.sqrt(distSq);

                dx /= dist;
                dy /= dist;

                a.vx -= dx * force * 0.01;
                a.vy -= dy * force * 0.01;
                b.vx += dx * force * 0.01;
                b.vy += dy * force * 0.01;
            }
        }

        edges.forEach(edge => {
            const a = nodeById.get(edge.source);
            const b = nodeById.get(edge.target);

            if (!a || !b) return;

            let dx = b.x - a.x;
            let dy = b.y - a.y;
            let dist = Math.sqrt(dx * dx + dy * dy) || 1;

            const ideal = 1500 - edge.score * 900;

            dx /= dist;
            dy /= dist;

            const clusterPull = edge.score * 0.022;

            a.vx += dx * clusterPull;
            a.vy += dy * clusterPull;
            b.vx -= dx * clusterPull;
            b.vy -= dy * clusterPull;
        });

        nodes.forEach(node => {
            node.vx += (cx - node.x) * 0.00008;
            node.vy += (cy - node.y) * 0.00008;

            node.vx *= 0.9;
            node.vy *= 0.9;

            node.x += node.vx;
            node.y += node.vy;

            node.x = clamp(node.x, -width * 2, width * 3);
            node.y = clamp(node.y, -height * 2, height * 3);
        });
    }
}

function trimName(name, max = 22) {
    if (!name) return "";
    return name.length > max ? name.slice(0, max - 1) + "…" : name;
}

function formatDuration(ms) {
    if (!ms || ms <= 0) return "—";

    const totalSec = Math.floor(ms / 1000);

    const hours = Math.floor(totalSec / 3600);
    const minutes = Math.floor((totalSec % 3600) / 60);

    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }

    return `${minutes}m`;
}

function wrapText(ctx, text, maxWidth) {
    const words = String(text || "").split(" ");
    const lines = [];
    let current = "";

    words.forEach(word => {
        const test = current ? `${current} ${word}` : word;
        if (ctx.measureText(test).width <= maxWidth) {
            current = test;
        } else {
            if (current) lines.push(current);
            current = word;
        }
    });

    if (current) lines.push(current);
    return lines.slice(0, 2);
}

function filterEdges(edges) {

    const byNode = new Map();

    for (const e of edges) {

        if (e.score <= 0) continue;

        if (!byNode.has(e.source)) byNode.set(e.source, []);
        if (!byNode.has(e.target)) byNode.set(e.target, []);

        byNode.get(e.source).push(e);
        byNode.get(e.target).push(e);
    }

    const kept = new Set();

    for (const list of byNode.values()) {
        list
            .sort((a, b) => b.score - a.score)
            .slice(0, 4)
            .forEach(e => kept.add(e));
    }

    return [...kept];
}

function ensureNodeConnectivity(edges, visibleEdges) {

    const bestEdgeByNode = new Map();

    edges.forEach(e => {

        if (e.score <= 0) return;

        const currentA = bestEdgeByNode.get(e.source);
        if (!currentA || e.score > currentA.score) {
            bestEdgeByNode.set(e.source, e);
        }

        const currentB = bestEdgeByNode.get(e.target);
        if (!currentB || e.score > currentB.score) {
            bestEdgeByNode.set(e.target, e);
        }

    });

    bestEdgeByNode.forEach(e => visibleEdges.add(e));

    return [...visibleEdges].filter(e => e.score > 0);
}

function getVisibleEdges(edges, zoom) {

    const positive = edges.filter(e => e.score > 0);

    let filtered = filterEdges(positive);

    filtered = filtered.filter(e => {

        if (zoom < 0.45) return e.score > 0.50;
        if (zoom < 0.8) return e.score > 0.38;
        if (zoom < 1.3) return e.score > 0.26;
        if (zoom < 2.0) return e.score > 0.18;

        return true;

    });

    filtered = ensureNodeConnectivity(positive, new Set(filtered));

    if (filtered.length < 10 && positive.length > 0) {
        filtered = [...positive]
            .sort((a, b) => b.score - a.score)
            .slice(0, 10);
    }

    return filtered;
}

function moveHoverCard(card, e) {

    const pad = 18;

    const rect = card.getBoundingClientRect();
    const w = rect.width || 320;
    const h = rect.height || 200;

    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let x = e.clientX + pad;
    let y = e.clientY + pad;

    const centerBias = e.clientX < vw * 0.5 ? 1 : -1;

    if (x + w > vw) {
        x = e.clientX - w - pad;
    }

    if (y + h > vh) {
        y = e.clientY - h - pad;
    }

    // bias away from mouse center so it doesn't sit on the graph object
    x += centerBias * 10;

    card.style.left = `${x}px`;
    card.style.top = `${y}px`;
}

function syncSidebarSelection(selectedId) {

    const items = document.querySelectorAll(".ws-sidebar-item");

    items.forEach(el => {

        const onclick = el.getAttribute("onclick");
        if (!onclick) return;

        const match = onclick.match(/selectWorkspacePlaylist\('(.+?)'/);
        if (!match) return;

        const id = match[1];

        if (id === selectedId) {
            el.classList.add("active");
            el.scrollIntoView({ block: "nearest" });
        } else {
            el.classList.remove("active");
        }

    });
}

export function renderRelationships(data) {

    if (relationshipAnimId) {
        cancelAnimationFrame(relationshipAnimId);
        relationshipAnimId = null;
    }

    if (relationshipCleanup) {
        relationshipCleanup();
        relationshipCleanup = null;
    }

    const out = document.getElementById("wsAnalyticsOutput");

    const playlists = data?.playlists || [];
    let edges = (data?.edges || []).map(e => ({ ...e }));

    if (playlists.length < 2) {
        out.innerHTML = `
        <div class="ws-rel-empty">
            Select at least two playlists to map relationships.
        </div>
        `;
        return;
    }

    const positiveEdges = getPositiveEdges(edges);

    const strongestEdge = [...positiveEdges].sort((a, b) => b.score - a.score)[0] || null;
    const avgScore = positiveEdges.length
        ? (positiveEdges.reduce((sum, e) => sum + e.score, 0) / positiveEdges.length)
        : 0;

    out.innerHTML = `
    <div class="ws-rel-full">

        <span 
            class="ws-panel-help ws-help"
            data-tooltip="This page shows you the connections between your selected playlists. The brighter an edge and the closer two playlist are, the more alike they are. Calculated using the weighted sliders. Hover and edge or a node for more info.

            Track - Tracks appearing in both playlists.
            Duration - Playlist listen times.
            ">
        Help
        </span>

        <div class="ws-header">

            <div class="ws-title">
                Average Similarity:
                <span class="ws-title-number">
                    ${(avgScore * 100).toFixed(1)}%
                </span>
            </div>

            <div class="ws-rel-weight-controls">

                <div class="ws-rel-weight">
                    <label>Genres</label>
                    <input type="range" id="relGenre" min="0" max="100">
                    <span id="relGenreVal">35%</span>
                    <button class="ws-rel-lock" data-lock="genre"></button>
                </div>

                <div class="ws-rel-weight">
                    <label>Artists</label>
                    <input type="range" id="relArtist" min="0" max="100">
                    <span id="relArtistVal">25%</span>
                    <button class="ws-rel-lock" data-lock="artist"></button>
                </div>

                <div class="ws-rel-weight">
                    <label>Tracks</label>
                    <input type="range" id="relTrack" min="0" max="100">
                    <span id="relTrackVal">15%</span>
                    <button class="ws-rel-lock" data-lock="track"></button>
                </div>

                <div class="ws-rel-weight">
                    <label>Albums</label>
                    <input type="range" id="relAlbum" min="0" max="100">
                    <span id="relAlbumVal">10%</span>
                    <button class="ws-rel-lock" data-lock="album"></button>
                </div>

                <div class="ws-rel-weight">
                    <label>Decades</label>
                    <input type="range" id="relDecade" min="0" max="100">
                    <span id="relDecadeVal">5%</span>
                    <button class="ws-rel-lock" data-lock="decade"></button>
                </div>

                <div class="ws-rel-weight">
                    <label>Duration</label>
                    <input type="range" id="relDuration" min="0" max="100">
                    <span id="relDurationVal">10%</span>
                    <button class="ws-rel-lock" data-lock="duration"></button>
                </div>

            </div>

        </div>

        <div class="ws-rel-chart">
            <canvas id="wsRelationshipCanvas"></canvas>
        </div>

        <div id="wsRelHoverCard" class="ws-rel-hover-card hidden">
            <div class="ws-rel-hover-title"></div>
            <div class="ws-rel-hover-meta"></div>
            <div class="ws-rel-hover-break"></div>
        </div>

    </div>
    `;

    const canvas = document.getElementById("wsRelationshipCanvas");
    const wrap = canvas.parentElement;
    const hoverCard = document.getElementById("wsRelHoverCard");

    const dpr = window.devicePixelRatio || 1;
    const width = Math.floor(wrap.clientWidth);
    const height = Math.floor(wrap.clientHeight);

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = "100%";
    canvas.style.height = "100%";

    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);

    const nodeMap = buildNodeMap(playlists);

    let hoveredNode = null;
    let hoveredEdge = null;

    const nodes = [...nodeMap.values()];
    const graphSignature = getGraphSignature(playlists);

    const genreSlider = document.getElementById("relGenre");
    const artistSlider = document.getElementById("relArtist");
    const albumSlider = document.getElementById("relAlbum");
    const decadeSlider = document.getElementById("relDecade");
    const trackSlider = document.getElementById("relTrack");
    const durationSlider = document.getElementById("relDuration");

    const avgScoreEl = out.querySelector(".ws-title-number");

    const weightEls = {
        genre: document.getElementById("relGenreVal"),
        artist: document.getElementById("relArtistVal"),
        album: document.getElementById("relAlbumVal"),
        decade: document.getElementById("relDecadeVal"),
        track: document.getElementById("relTrackVal"),
        duration: document.getElementById("relDurationVal")
    };

    const sliders = {
        genre: genreSlider,
        artist: artistSlider,
        album: albumSlider,
        decade: decadeSlider,
        track: trackSlider,
        duration: durationSlider
    };

    syncSlidersFromWeights(sliders, weightEls);

    const lockButtons = document.querySelectorAll(".ws-rel-lock");

    lockButtons.forEach(btn => {

        btn.addEventListener("click", () => {

            const key = btn.dataset.lock;

            const lockedCount = Object.values(lockedWeights).filter(v => v).length;

            if (!lockedWeights[key] && lockedCount >= 3) return;

            lockedWeights[key] = !lockedWeights[key];

            btn.classList.toggle("locked");
            sliders[key].disabled = lockedWeights[key];

        });

    });

    Object.entries(sliders).forEach(([key, slider]) => {

        slider.addEventListener("input", () => {

            const raw = Number(slider.value);
            applySliderValue(key, raw);
            slider.value = clamp(weights[key], 0, 100);

            syncSlidersFromWeights(sliders, weightEls);
            recomputeScores(edges, avgScoreEl, weightEls);
            updateStrongestEdge(edges);

            runLayout(nodes, getPositiveEdges(edges), width, height);
            saveGraphState(nodes);
        });

    });

    recomputeScores(edges, avgScoreEl, weightEls);
    updateStrongestEdge(edges);

    const canRestoreLayout =
        relationshipGraphState.signature === graphSignature &&
        restoreGraphState(nodes);

    if (!canRestoreLayout) {
        initializeNodePositions(nodes, width, height);
        runLayout(nodes, getPositiveEdges(edges), width, height);

        zoom = 1;
        targetZoom = 1;
        panX = 0;
        panY = 0;

        relationshipGraphState.signature = graphSignature;
        saveGraphState(nodes);
    }

    let currentVisibleEdges = [];
    let strongestHoveredNodeEdge = null;
    let pulse = 0;

    function getStrongestEdgeForNode(nodeId) {
        let best = null;

        for (const edge of currentVisibleEdges) {
            if (edge.source !== nodeId && edge.target !== nodeId) continue;
            if (!best || edge.score > best.score) {
                best = edge;
            }
        }

        return best;
    }

    function renderHoverRows(items) {
        if (!items || !items.length) return "—";
        return items
            .map(i => `<div class="ws-rel-pill">${escapeHtml(String(i))}</div>`)
            .join("");
    }

    function drawEdge(edge, isHovered, isStrongest, isNodeStrongest) {
        const a = nodeMap.get(edge.source);
        const b = nodeMap.get(edge.target);
        if (!a || !b) return;

        ctx.save();

        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);

        let width = scoreToWidth(edge.score);
        let color = scoreToStroke(edge.score);
        let glow = 0;

        if (isStrongest) {
            width += 0.5;
            color = "rgba(29,185,84,0.95)";
            glow = 8;
        }

        if (isHovered) {
            width += 2;
            color = "rgba(29,185,84,1)";
            glow = 24;
        }

        if (isNodeStrongest) {
            width += 1.4;
            color = "rgba(29,185,84,0.85)";
            glow = 14;
        }

        ctx.lineWidth = width;
        ctx.strokeStyle = color;
        ctx.shadowBlur = glow;
        ctx.shadowColor = "rgba(29,185,84,0.9)";

        ctx.stroke();

        const mx = (a.x + b.x) / 2;
        const my = (a.y + b.y) / 2;

        ctx.fillStyle = isHovered ? "rgba(29,185,84,0.95)" : "rgba(255,255,255,0.18)";
        
        const edgeText = clamp(
            12 / Math.pow(zoom, 0.4),
            10,
            16
        );

        ctx.font = `${edgeText}px Inter, sans-serif`;
        ctx.textAlign = "center";
        if (zoom > 0.6 || isHovered) {
            ctx.fillText(`${Math.round(edge.score * 100)}%`, mx, my - 8);
        }
        ctx.restore();
    }

    function drawNode(node, isHovered) {
        const base = 18 + Math.sqrt(node.track_count) * 2.2;

        const zoomScale = Math.pow(zoom, 0.7);

        const radius = clamp(
            base / zoomScale,
            18,
            64
        );
        const ring = isHovered ? 10 + Math.sin(pulse) * 2 : 0;

        ctx.save();

        if (isHovered) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius + ring, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(29,185,84,0.08)";
            ctx.fill();
        }

        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
        ctx.closePath();
        ctx.clip();

        if (node.img && node.img.complete) {

            const size = Math.min(node.img.width, node.img.height);

            ctx.drawImage(
                node.img,
                (node.img.width - size) / 2,
                (node.img.height - size) / 2,
                size,
                size,
                node.x - radius,
                node.y - radius,
                radius * 2,
                radius * 2
            );

        } else {

            ctx.fillStyle = "rgba(12,18,30,0.94)";
            ctx.fill();

        }

        ctx.restore();
        ctx.save();

        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);

        ctx.lineWidth = isHovered ? 3 : 1.2;

        ctx.strokeStyle = isHovered
            ? "rgba(29,185,84,0.9)"
            : "rgba(255,255,255,0.06)";

        ctx.shadowBlur = isHovered ? 18 : 0;
        ctx.shadowColor = "rgba(29,185,84,0.55)";

        ctx.stroke();
        ctx.restore();
    }

    function render() {

        pulse += 0.08;

        const prevZoom = zoom;

        zoom += (targetZoom - zoom) * 0.18;

        const zoomFactor = zoom / prevZoom;

        panX = mouseX - (mouseX - panX) * zoomFactor;
        panY = mouseY - (mouseY - panY) * zoomFactor;

        ctx.clearRect(0, 0, width, height);

        ctx.save();

        ctx.translate(panX, panY);
        ctx.scale(zoom, zoom);

        const visibleEdges = getVisibleEdges(edges, zoom);

        const activeNodeId = hoveredNode?.playlist_id || selectedNodeId || null;

        strongestHoveredNodeEdge = activeNodeId
            ? getStrongestEdgeForNode(activeNodeId)
            : null;

        currentVisibleEdges = visibleEdges;

        const strongestEdgeDynamic = strongestEdgeGlobal;

        currentVisibleEdges.forEach(edge =>
            drawEdge(
                edge,
                hoveredEdge === edge,
                strongestEdgeDynamic &&
                edge.source === strongestEdgeDynamic.source &&
                edge.target === strongestEdgeDynamic.target,
                strongestHoveredNodeEdge === edge
            )
        );
        
        nodes.forEach(node => {

            let highlight = false;

            if (
                node === hoveredNode ||
                node.playlist_id === selectedNodeId
            ) {
                highlight = true;
            }

            const activeEdge = hoveredEdge || (
                selectedEdgeKey
                    ? currentVisibleEdges.find(e => getEdgeKey(e) === selectedEdgeKey) || null
                    : null
            );

            if (activeEdge) {
                if (
                    node.playlist_id === activeEdge.source ||
                    node.playlist_id === activeEdge.target
                ) {
                    highlight = true;
                }
            }

            const activeNodeId = hoveredNode?.playlist_id || selectedNodeId;

            if (activeNodeId && strongestHoveredNodeEdge) {

                const otherId =
                    strongestHoveredNodeEdge.source === activeNodeId
                        ? strongestHoveredNodeEdge.target
                        : strongestHoveredNodeEdge.source;

                if (node.playlist_id === otherId) {
                    highlight = true;
                }
            }

            drawNode(node, highlight);

        });

        ctx.restore();

        relationshipGraphState.signature = graphSignature;
        saveGraphState(nodes);

        relationshipAnimId = requestAnimationFrame(render);
    }

    function distanceToSegment(px, py, x1, y1, x2, y2) {
        const dx = x2 - x1;
        const dy = y2 - y1;

        if (dx === 0 && dy === 0) {
            return Math.hypot(px - x1, py - y1);
        }

        const t = clamp(
            ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy),
            0,
            1
        );

        const sx = x1 + t * dx;
        const sy = y1 + t * dy;

        return Math.hypot(px - sx, py - sy);
    }

        function handleWheel(e) {
        e.preventDefault();

        const rect = canvas.getBoundingClientRect();
        const localX = e.clientX - rect.left;
        const localY = e.clientY - rect.top;

        mouseX = localX;
        mouseY = localY;

        const zoomIntensity = 0.0008;

        targetZoom += -e.deltaY * zoomIntensity;
        targetZoom = clamp(targetZoom, 0.4, 2);
    }

    function handleMouseDown(e) {
        dragging = true;
        dragStartX = e.clientX - panX;
        dragStartY = e.clientY - panY;
    }

    function handleMouseUp() {
        dragging = false;
        saveGraphState(nodes);
    }

    function handleMouseMove(e) {
        const bounds = canvas.getBoundingClientRect();

        mouseX = e.clientX - bounds.left;
        mouseY = e.clientY - bounds.top;

        if (dragging) {
            panX = e.clientX - dragStartX;
            panY = e.clientY - dragStartY;
            return;
        }

        const mx = (e.clientX - bounds.left - panX) / zoom;
        const my = (e.clientY - bounds.top - panY) / zoom;

        hoveredNode = null;
        hoveredEdge = null;

        for (const node of nodes) {
            const radius = clamp(
                (26 + Math.sqrt(node.track_count) * 1.8) / Math.pow(zoom, 0.35),
                14,
                60
            );

            const dist = Math.hypot(mx - node.x, my - node.y);

            if (dist <= radius) {
                hoveredNode = node;
                break;
            }
        }

        if (!hoveredNode) {
            for (const edge of currentVisibleEdges) {
                const a = nodeMap.get(edge.source);
                const b = nodeMap.get(edge.target);
                if (!a || !b) continue;

                const dist = distanceToSegment(mx, my, a.x, a.y, b.x, b.y);
                if (dist <= 10) {
                    hoveredEdge = edge;
                    break;
                }
            }
        }

        if (hoveredNode) {

            canvas.style.cursor = "pointer";

            hoverCard.classList.remove("hidden");
            moveHoverCard(hoverCard, e);

            hoverCard.querySelector(".ws-rel-hover-title").textContent =
                hoveredNode.playlist_name;

            hoverCard.querySelector(".ws-rel-hover-meta").textContent =
                `${hoveredNode.track_count} tracks • ${formatDuration(hoveredNode.total_duration)}`;

            hoverCard.querySelector(".ws-rel-hover-break").innerHTML = `
                <div class="ws-rel-hover-section">
                    <div class="ws-rel-hover-label">Top Genres</div>
                    <div class="ws-rel-hover-pills">
                        ${renderHoverRows(hoveredNode.top_genres)}
                    </div>
                </div>

                <div class="ws-rel-hover-section">
                    <div class="ws-rel-hover-label">Top Artists</div>
                    <div class="ws-rel-hover-pills">
                        ${renderHoverRows(hoveredNode.top_artists)}
                    </div>
                </div>

                <div class="ws-rel-hover-section">
                    <div class="ws-rel-hover-label">Dominant Album</div>
                    <div class="ws-rel-hover-pills">
                        ${renderHoverRows(
                            hoveredNode.dominant_album && hoveredNode.dominant_album !== "-"
                                ? [hoveredNode.dominant_album]
                                : []
                        )}
                    </div>
                </div>

                <div class="ws-rel-hover-section">
                    <div class="ws-rel-hover-label">Dominant Era</div>
                    <div class="ws-rel-hover-pills">
                        ${renderHoverRows(
                            hoveredNode.dominant_decade && hoveredNode.dominant_decade !== "-"
                                ? [hoveredNode.dominant_decade + "s"]
                                : []
                        )}
                    </div>
                </div>
            `;

        } else if (hoveredEdge) {

            const a = nodeMap.get(hoveredEdge.source);
            const b = nodeMap.get(hoveredEdge.target);

            hoverCard.classList.remove("hidden");
            moveHoverCard(hoverCard, e);

            hoverCard.querySelector(".ws-rel-hover-title").textContent =
                `${a.playlist_name} ↔ ${b.playlist_name}`;

            const aNode = nodeMap.get(hoveredEdge.source);
            const bNode = nodeMap.get(hoveredEdge.target);

            hoverCard.querySelector(".ws-rel-hover-meta").textContent =
                `${Math.round(hoveredEdge.score * 100)}% similarity • ${formatDuration(aNode?.total_duration)} vs ${formatDuration(bNode?.total_duration)}`;

            const formatList = list =>
                list && list.length ? list.join("<br>") : "None";

            let sections = "";

            if (hoveredEdge.shared_tracks > 0) {
                const tracksHtml = (hoveredEdge.track_overlap_sample || []).map(t => {
                    const artists = (t.artists || []).join(", ");
                    return `${escapeHtml(t.name)} — ${escapeHtml(artists)}`;
                }).join("<br>");

                sections += `
                <div class="ws-rel-hover-section">
                    <div class="ws-rel-hover-label">
                        Shared Songs (${hoveredEdge.shared_tracks})
                    </div>
                    <div class="ws-rel-hover-list">
                        ${tracksHtml || "—"}
                    </div>
                </div>`;
            }

            if (weights.genre > 0) {
                sections += `
                <div class="ws-rel-hover-section">
                    <div class="ws-rel-hover-label">
                        Overlapping Genres
                    </div>
                    <div class="ws-rel-hover-list">
                        ${formatList(hoveredEdge.genre_overlap)}
                    </div>
                </div>`;
            }

            if (weights.artist > 0) {
                sections += `
                <div class="ws-rel-hover-section">
                    <div class="ws-rel-hover-label">
                        Overlapping Artists
                    </div>
                    <div class="ws-rel-hover-list">
                        ${formatList(hoveredEdge.artist_overlap)}
                    </div>
                </div>`;
            }

            if (weights.album > 0) {
                sections += `
                <div class="ws-rel-hover-section">
                    <div class="ws-rel-hover-label">
                        Overlapping Albums
                    </div>
                    <div class="ws-rel-hover-list">
                        ${formatList(hoveredEdge.album_overlap)}
                    </div>
                </div>`;
            }

            if (weights.decade > 0) {
                sections += `
                <div class="ws-rel-hover-section">
                    <div class="ws-rel-hover-label">
                        Overlapping Decades
                    </div>
                    <div class="ws-rel-hover-list">
                        ${
                            hoveredEdge.decade_overlap && hoveredEdge.decade_overlap.length
                                ? hoveredEdge.decade_overlap.map(d => `${d}s`).join("<br>")
                                : "None"
                        }
                    </div>
                </div>`;
            }

            hoverCard.querySelector(".ws-rel-hover-break").innerHTML = sections;

        } else {
            canvas.style.cursor = "default";
            hoverCard.classList.add("hidden");
        }
    }

    function handleMouseLeave() {
        hoveredNode = null;
        hoveredEdge = null;
        canvas.style.cursor = "default";
        hoverCard.classList.add("hidden");
    }

    function handleCanvasClick() {

        if (hoveredNode) {

            const playlistId = hoveredNode.playlist_id;

            selectedNodeId = playlistId;
            selectedEdgeKey = null;

            syncSidebarSelection(selectedNodeId);

            setCurrentSelection(playlistId);
            window.maybeRenderAnalytics?.();

            return;
        }

        if (hoveredEdge) {
            selectedEdgeKey = getEdgeKey(hoveredEdge);
            selectedNodeId = null;

            syncSidebarSelection(null);
            return;
        }

        selectedNodeId = null;
        selectedEdgeKey = null;

        syncSidebarSelection(null);
    }

    function handleSidebarClick(e) {
        const card = e.target.closest(".ws-sidebar-item");
        if (!card) return;

        const onclick = card.getAttribute("onclick");
        if (!onclick) return;

        const match = onclick.match(/selectWorkspacePlaylist\('(.+?)'/);
        if (!match) return;

        const playlistId = match[1];
        if (!nodeMap.has(playlistId)) return;

        selectedNodeId = playlistId;
        selectedEdgeKey = null;

        syncSidebarSelection(selectedNodeId);
    }

    canvas.addEventListener("wheel", handleWheel, { passive: false });
    canvas.addEventListener("mousedown", handleMouseDown);
    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mouseleave", handleMouseLeave);
    canvas.addEventListener("click", handleCanvasClick);
    document.addEventListener("click", handleSidebarClick);
    window.addEventListener("mouseup", handleMouseUp);

    relationshipCleanup = () => {
        canvas.removeEventListener("wheel", handleWheel);
        canvas.removeEventListener("mousedown", handleMouseDown);
        canvas.removeEventListener("mousemove", handleMouseMove);
        canvas.removeEventListener("mouseleave", handleMouseLeave);
        canvas.removeEventListener("click", handleCanvasClick);
        document.removeEventListener("click", handleSidebarClick);
        window.removeEventListener("mouseup", handleMouseUp);
    };

    render();
}