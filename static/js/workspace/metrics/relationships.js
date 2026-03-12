import { escapeHtml } from "../utils.js";

let relationshipAnimId = null;

let zoom = 1;
let targetZoom = 1;
let panX = 0;
let panY = 0;
let mouseX = 0;
let mouseY = 0;

let dragging = false;
let dragStartX = 0;
let dragStartY = 0;

let weights = {
    genre: 50,
    artist: 35,
    album: 10,
    decade: 5
};

let lockedWeights = {
    genre: false,
    artist: false,
    album: false,
    decade: false
};

function recomputeScores(edges, scoreEl, weightEls) {

    const total =
        weights.genre +
        weights.artist +
        weights.album +
        weights.decade;

    if (total <= 0) {
        weights.genre = 100;
        weights.artist = 0;
        weights.album = 0;
        weights.decade = 0;
    }

    const safeTotal =
        weights.genre +
        weights.artist +
        weights.album +
        weights.decade;

    const g = weights.genre / safeTotal;
    const a = weights.artist / safeTotal;
    const al = weights.album / safeTotal;
    const d = weights.decade / safeTotal;

    let scoreSum = 0;

    edges.forEach(e => {

        const newScore =
            g * e.genre_score +
            a * e.artist_score +
            al * e.album_score +
            d * e.decade_score;

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

function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
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

        if (!byNode.has(e.source)) byNode.set(e.source, []);
        if (!byNode.has(e.target)) byNode.set(e.target, []);

        byNode.get(e.source).push(e);
        byNode.get(e.target).push(e);
    }

    const kept = new Set();

    for (const list of byNode.values()) {

        list
            .sort((a,b) => b.score - a.score)
            .slice(0, 4)      // keep top 4 per playlist
            .forEach(e => kept.add(e));
    }

    return [...kept];
}

function ensureNodeConnectivity(edges, visibleEdges) {

    const connected = new Set();

    visibleEdges.forEach(e => {
        connected.add(e.source);
        connected.add(e.target);
    });

    const bestEdgeByNode = new Map();

    edges.forEach(e => {

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

    return [...visibleEdges];
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

export function renderRelationships(data) {

    if (relationshipAnimId) {
        cancelAnimationFrame(relationshipAnimId);
        relationshipAnimId = null;
    }

    const out = document.getElementById("wsAnalyticsOutput");

    const playlists = data?.playlists || [];
    let edges = (data?.edges || []).filter(e => e.score > 0);

    if (playlists.length < 2) {
        out.innerHTML = `
        <div class="ws-rel-empty">
            Select at least two playlists to map relationships.
        </div>
        `;
        return;
    }

    const strongestEdge = [...edges].sort((a, b) => b.score - a.score)[0] || null;
    const avgScore = edges.length
        ? (edges.reduce((sum, e) => sum + e.score, 0) / edges.length)
        : 0;

    out.innerHTML = `
    <div class="ws-rel-full">

        <div class="ws-avg-header">

            <div class="ws-avg-title">
                Average Similarity:
                <span class="ws-avg-inline-number">
                    ${(avgScore * 100).toFixed(1)}%
                </span>
            </div>

            <div class="ws-rel-weight-controls">

                <div class="ws-rel-weight-group">

                    <div class="ws-rel-weight">
                        <label>Genres</label>
                        <input type="range" id="relGenre" min="0" max="100" value="50">
                        <span id="relGenreVal">50%</span>
                        <button class="ws-rel-lock" data-lock="genre">🔒</button>
                    </div>

                    <div class="ws-rel-weight">
                        <label>Artists</label>
                        <input type="range" id="relArtist" min="0" max="100" value="35">
                        <span id="relArtistVal">35%</span>
                        <button class="ws-rel-lock" data-lock="artist">🔒</button>
                    </div>

                </div>

                <div class="ws-rel-weight-group">

                    <div class="ws-rel-weight">
                        <label>Albums</label>
                        <input type="range" id="relAlbum" min="0" max="100" value="10">
                        <span id="relAlbumVal">10%</span>
                        <button class="ws-rel-lock" data-lock="album">🔒</button>
                    </div>

                    <div class="ws-rel-weight">
                        <label>Decades</label>
                        <input type="range" id="relDecade" min="0" max="100" value="5">
                        <span id="relDecadeVal">5%</span>
                        <button class="ws-rel-lock" data-lock="decade">🔒</button>
                    </div>

                </div>

            </div>

            <span
                class="ws-panel-help ws-help ws-rel-chart-help"
                data-tooltip="Each node is a playlist.

    Each line represents similarity between playlists.

    Adjust weighting sliders to explore relationships."
            >?</span>

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

    document.addEventListener("click", e => {

        const card = e.target.closest(".ws-sidebar-item");
        if (!card) return;

        const onclick = card.getAttribute("onclick");
        if (!onclick) return;

        const match = onclick.match(/selectWorkspacePlaylist\('(.+?)'/);

        if (!match) return;

        const playlistId = match[1];

        const node = nodeMap.get(playlistId);
        if (!node) return;

        hoveredNode = node;

    });

    const nodes = [...nodeMap.values()];

    const genreSlider = document.getElementById("relGenre");
    const artistSlider = document.getElementById("relArtist");
    const albumSlider = document.getElementById("relAlbum");
    const decadeSlider = document.getElementById("relDecade");

    const avgScoreEl = out.querySelector(".ws-avg-inline-number");

    const weightEls = {
        genre: document.getElementById("relGenreVal"),
        artist: document.getElementById("relArtistVal"),
        album: document.getElementById("relAlbumVal"),
        decade: document.getElementById("relDecadeVal")
    };

    const sliders = {
        genre: genreSlider,
        artist: artistSlider,
        album: albumSlider,
        decade: decadeSlider
    };

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
            slider.value = clamp(weights[key],0,100);

            genreSlider.value = clamp(Math.round(weights.genre),0,100);
            artistSlider.value = clamp(Math.round(weights.artist),0,100);
            albumSlider.value = clamp(Math.round(weights.album),0,100);
            decadeSlider.value = clamp(Math.round(weights.decade),0,100);

            recomputeScores(edges, avgScoreEl, weightEls);
            runLayout(nodes, edges, width, height);
        });

    });

    recomputeScores(edges, avgScoreEl, weightEls);
    initializeNodePositions(nodes, width, height);
    runLayout(nodes, edges, width, height);

    runLayout(nodes, edges, width, height);

    let hoveredNode = null;
    let hoveredEdge = null;
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

        let filteredEdges = filterEdges(edges);

        strongestHoveredNodeEdge = hoveredNode
            ? getStrongestEdgeForNode(hoveredNode.playlist_id)
            : null;

        let visibleEdges = filteredEdges.filter(e => {

            if (zoom < 0.45) return e.score > 0.50;
            if (zoom < 0.8) return e.score > 0.38;
            if (zoom < 1.3) return e.score > 0.26;
            if (zoom < 2.0) return e.score > 0.18;

            return true;

        });

        visibleEdges = ensureNodeConnectivity(edges, new Set(visibleEdges));

        if (visibleEdges.length < 10) {
            visibleEdges = [...edges]
                .sort((a,b) => b.score - a.score)
                .slice(0,10);
        }

        currentVisibleEdges = visibleEdges;

        const strongestEdgeDynamic =
            [...edges].sort((a,b)=>b.score-a.score)[0];

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

            if (hoveredNode && node === hoveredNode) {
                highlight = true;
            }

            if (hoveredEdge) {
                if (
                    node.playlist_id === hoveredEdge.source ||
                    node.playlist_id === hoveredEdge.target
                ) {
                    highlight = true;
                }
            }

            if (hoveredNode && strongestHoveredNodeEdge) {

                const otherId =
                    strongestHoveredNodeEdge.source === hoveredNode.playlist_id
                        ? strongestHoveredNodeEdge.target
                        : strongestHoveredNodeEdge.source;

                if (node.playlist_id === otherId) {
                    highlight = true;
                }
            }

            drawNode(node, highlight);

        });

        ctx.restore();

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

    canvas.addEventListener("wheel", e => {

        e.preventDefault();

        const zoomIntensity = 0.0008;

        targetZoom += -e.deltaY * zoomIntensity;
        targetZoom = clamp(targetZoom, 0.4, 2);

    });

    canvas.addEventListener("mousedown", e => {

        dragging = true;

        dragStartX = e.clientX - panX;
        dragStartY = e.clientY - panY;

    });

    window.addEventListener("mouseup", () => {

        dragging = false;

    });

    canvas.addEventListener("mousemove", e => {

        const rect = canvas.getBoundingClientRect();

        mouseX = e.clientX - rect.left;
        mouseY = e.clientY - rect.top;

    });

    canvas.addEventListener("mousemove", e => {

        if (!dragging) return;

        panX = e.clientX - dragStartX;
        panY = e.clientY - dragStartY;

    });

    canvas.addEventListener("mousemove", e => {
        const bounds = canvas.getBoundingClientRect();

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
                `${hoveredNode.track_count} tracks`;

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

            hoverCard.querySelector(".ws-rel-hover-meta").textContent =
                `${Math.round(hoveredEdge.score * 100)}% similarity`;

            const formatList = list =>
                list && list.length ? list.join("<br>") : "None";

            let sections = "";

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
    });

    canvas.addEventListener("mouseleave", () => {
        hoveredNode = null;
        hoveredEdge = null;
        canvas.style.cursor = "default";
        hoverCard.classList.add("hidden");
    });

    canvas.addEventListener("click", () => {

        if (!hoveredNode) return;

        const playlistId = hoveredNode.playlist_id;

        const cards = document.querySelectorAll(".ws-sidebar-item");

        for (const card of cards) {

            if (card.getAttribute("onclick")?.includes(playlistId)) {

                card.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });

                window.selectWorkspacePlaylist(playlistId, card);

                break;
            }
        }

    });

    render();
}