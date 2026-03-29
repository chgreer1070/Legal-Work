/**
 * ContractTwin 3D — Three.js interactive visualization for EMS contracts.
 *
 * Renders clause nodes in 6 zones, dependency edges with animated particles,
 * raycaster interaction, scenario cascade playback, and economics overlays.
 */

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

// ── State ────────────────────────────────────────────────────────────────────

let contractData = null;       // Full API response
let scene, camera, renderer, controls;
let nodeMeshes = [];           // {mesh, clause, glow}
let edgeGroups = [];           // {group, particles[], curve, edge}
let zoneGroups = {};           // zone_name -> THREE.Group
let selectedNode = null;
let hoveredNode = null;
let viewMode = "risk";         // "risk" | "economics"
let raycaster, mouse;
let animFrame = 0;
let scenarioRunning = false;

// DOM refs
const canvas       = document.getElementById("twinCanvas");
const tooltip      = document.getElementById("tooltip");
const detailPanel  = document.getElementById("detailPanel");
const detailTitle  = document.getElementById("detailTitle");
const detailBody   = document.getElementById("detailBody");
const detailClose  = document.getElementById("detailClose");
const layout       = document.querySelector(".twin-layout");
const loadDemoBtn  = document.getElementById("loadDemoBtn");
const parseBtn     = document.getElementById("parseBtn");
const contractInput= document.getElementById("contractInput");
const loadingOverlay = document.getElementById("loadingOverlay");
const scenarioSelect = document.getElementById("scenarioSelect");
const runScenarioBtn = document.getElementById("runScenarioBtn");

// ── Init Three.js ────────────────────────────────────────────────────────────

function initScene() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0a1a);
  scene.fog = new THREE.FogExp2(0x0a0a1a, 0.008);

  camera = new THREE.PerspectiveCamera(55, 1, 0.1, 200);
  camera.position.set(0, 35, 45);

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;

  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.maxPolarAngle = Math.PI / 2.1;
  controls.minDistance = 10;
  controls.maxDistance = 80;
  controls.target.set(0, 2, 5);

  // Lights
  const ambient = new THREE.AmbientLight(0x334466, 0.6);
  scene.add(ambient);
  const dir1 = new THREE.DirectionalLight(0xffffff, 0.8);
  dir1.position.set(20, 30, 20);
  scene.add(dir1);
  const dir2 = new THREE.DirectionalLight(0x6688ff, 0.3);
  dir2.position.set(-20, 20, -10);
  scene.add(dir2);

  // Grid
  const grid = new THREE.GridHelper(80, 40, 0x1a1a3a, 0x111130);
  grid.position.y = -0.1;
  scene.add(grid);

  // Raycaster
  raycaster = new THREE.Raycaster();
  mouse = new THREE.Vector2();

  resize();
  window.addEventListener("resize", resize);
  canvas.addEventListener("mousemove", onMouseMove);
  canvas.addEventListener("click", onClick);
  canvas.addEventListener("dblclick", onDoubleClick);
}

function resize() {
  const wrap = document.getElementById("canvasWrap");
  const w = wrap.clientWidth;
  const h = wrap.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

// ── Zone rendering ───────────────────────────────────────────────────────────

function createZones(zones) {
  for (const [name, config] of Object.entries(zones)) {
    const group = new THREE.Group();
    group.name = name;
    const [cx, cy, cz] = config.position;

    // Transparent cylinder
    const geo = new THREE.CylinderGeometry(7, 7, 0.3, 32);
    const mat = new THREE.MeshPhongMaterial({
      color: new THREE.Color(config.color),
      transparent: true,
      opacity: 0.06,
      side: THREE.DoubleSide,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(cx, 0, cz);
    group.add(mesh);

    // Zone ring
    const ringGeo = new THREE.TorusGeometry(7, 0.06, 8, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(config.color),
      transparent: true,
      opacity: 0.25,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(cx, 0.2, cz);
    group.add(ring);

    // Label sprite
    const label = makeTextSprite(config.label, config.color);
    label.position.set(cx, 0.6, cz);
    label.scale.set(6, 1.5, 1);
    group.add(label);

    scene.add(group);
    zoneGroups[name] = group;
  }
}

function makeTextSprite(text, color) {
  const canvas2d = document.createElement("canvas");
  canvas2d.width = 512;
  canvas2d.height = 128;
  const ctx = canvas2d.getContext("2d");
  ctx.fillStyle = "transparent";
  ctx.fillRect(0, 0, 512, 128);
  ctx.font = "bold 36px -apple-system, sans-serif";
  ctx.fillStyle = color;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 256, 64);

  const tex = new THREE.CanvasTexture(canvas2d);
  tex.needsUpdate = true;
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, opacity: 0.7 });
  return new THREE.Sprite(mat);
}

// ── Node rendering ───────────────────────────────────────────────────────────

function createNodes(clauses) {
  nodeMeshes = [];
  for (const clause of clauses) {
    const pos = clause._position || [0, 2, 0];
    const risk = clause.risk_rating || 2;
    const radius = 0.4 + risk * 0.15;

    // Node color from zone
    const zoneColor = getZoneColor(clause.zone);

    // Main sphere
    const geo = new THREE.SphereGeometry(radius, 24, 24);
    const mat = new THREE.MeshPhongMaterial({
      color: zoneColor,
      emissive: zoneColor,
      emissiveIntensity: 0.15,
      shininess: 60,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(pos[0], pos[1], pos[2]);
    mesh.userData = { clause };
    scene.add(mesh);

    // Glow
    const glowGeo = new THREE.SphereGeometry(radius * 1.5, 16, 16);
    const glowMat = new THREE.MeshBasicMaterial({
      color: zoneColor,
      transparent: true,
      opacity: 0.08,
    });
    const glow = new THREE.Mesh(glowGeo, glowMat);
    glow.position.copy(mesh.position);
    scene.add(glow);

    nodeMeshes.push({ mesh, clause, glow, baseRadius: radius, zoneColor });
  }
}

function getZoneColor(zone) {
  const colors = {
    customer: 0x3b82f6,
    manufacturer: 0x10b981,
    supplier: 0x8b5cf6,
    financial: 0xf59e0b,
    risk: 0xef4444,
    exit: 0x6b7280,
  };
  return colors[zone] || 0x94a3b8;
}

// ── Edge rendering ───────────────────────────────────────────────────────────

function createEdges(graph) {
  edgeGroups = [];
  const nodePositions = {};
  for (const node of graph.nodes) {
    nodePositions[node.id] = node.position;
  }

  for (const edge of graph.edges) {
    const srcPos = nodePositions[edge.source];
    const tgtPos = nodePositions[edge.target];
    if (!srcPos || !tgtPos) continue;

    const src = new THREE.Vector3(srcPos[0], srcPos[1], srcPos[2]);
    const tgt = new THREE.Vector3(tgtPos[0], tgtPos[1], tgtPos[2]);
    const mid = new THREE.Vector3().lerpVectors(src, tgt, 0.5);
    mid.y += 2 + Math.random() * 1.5;

    const curve = new THREE.QuadraticBezierCurve3(src, mid, tgt);
    const points = curve.getPoints(40);

    // Line
    const effect = edge.interaction_effect || "additive";
    let lineColor, lineOpacity, lineWidth;
    if (effect === "cascading") {
      lineColor = 0xef4444;
      lineOpacity = 0.3;
    } else if (effect === "amplifying") {
      lineColor = 0xf59e0b;
      lineOpacity = 0.2;
    } else {
      lineColor = 0x475569;
      lineOpacity = 0.12;
    }

    const lineGeo = new THREE.BufferGeometry().setFromPoints(points);
    const lineMat = new THREE.LineBasicMaterial({
      color: lineColor,
      transparent: true,
      opacity: lineOpacity,
    });
    const line = new THREE.Line(lineGeo, lineMat);

    const group = new THREE.Group();
    group.add(line);
    group.userData = { edge };

    // Particles
    const particles = [];
    const particleCount = effect === "cascading" ? 3 : effect === "amplifying" ? 2 : 1;
    for (let i = 0; i < particleCount; i++) {
      const pGeo = new THREE.SphereGeometry(0.08, 8, 8);
      const pMat = new THREE.MeshBasicMaterial({
        color: lineColor,
        transparent: true,
        opacity: 0.6,
      });
      const p = new THREE.Mesh(pGeo, pMat);
      p.userData = { t: i / particleCount, speed: 0.003 + Math.random() * 0.002 };
      const pt = curve.getPoint(p.userData.t);
      p.position.copy(pt);
      group.add(p);
      particles.push(p);
    }

    scene.add(group);
    edgeGroups.push({ group, particles, curve, edge, lineMat });
  }
}

// ── Interaction ──────────────────────────────────────────────────────────────

function onMouseMove(event) {
  const rect = canvas.getBoundingClientRect();
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

  raycaster.setFromCamera(mouse, camera);
  const meshes = nodeMeshes.map(n => n.mesh);
  const hits = raycaster.intersectObjects(meshes);

  if (hits.length > 0) {
    const hit = hits[0].object;
    const clause = hit.userData.clause;
    if (hoveredNode !== hit) {
      resetHover();
      hoveredNode = hit;
      hit.scale.setScalar(1.3);
      canvas.style.cursor = "pointer";
    }
    showTooltip(event.clientX, event.clientY, clause);
  } else {
    resetHover();
    hideTooltip();
    canvas.style.cursor = "grab";
  }
}

function resetHover() {
  if (hoveredNode) {
    hoveredNode.scale.setScalar(1.0);
    hoveredNode = null;
  }
}

function onClick(event) {
  const rect = canvas.getBoundingClientRect();
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

  raycaster.setFromCamera(mouse, camera);
  const meshes = nodeMeshes.map(n => n.mesh);
  const hits = raycaster.intersectObjects(meshes);

  if (hits.length > 0) {
    const clause = hits[0].object.userData.clause;
    selectClause(clause);
    zoomToNode(hits[0].object);
  }
}

function onDoubleClick() {
  // Reset camera
  animateCamera(new THREE.Vector3(0, 35, 45), new THREE.Vector3(0, 2, 5));
  deselectAll();
}

function selectClause(clause) {
  selectedNode = clause;

  // Highlight connected edges
  for (const eg of edgeGroups) {
    const connected = eg.edge.source === clause.id || eg.edge.target === clause.id;
    eg.lineMat.opacity = connected ? 0.6 : 0.05;
    eg.particles.forEach(p => { p.material.opacity = connected ? 0.9 : 0.2; });
  }

  // Highlight connected nodes
  const connectedIds = new Set();
  connectedIds.add(clause.id);
  for (const eg of edgeGroups) {
    if (eg.edge.source === clause.id) connectedIds.add(eg.edge.target);
    if (eg.edge.target === clause.id) connectedIds.add(eg.edge.source);
  }
  for (const nm of nodeMeshes) {
    const connected = connectedIds.has(nm.clause.id);
    nm.mesh.material.opacity = connected ? 1.0 : 0.2;
    nm.mesh.material.transparent = !connected;
    nm.glow.material.opacity = connected ? 0.15 : 0.02;
  }

  showDetailPanel(clause);
}

function deselectAll() {
  selectedNode = null;
  for (const eg of edgeGroups) {
    const effect = eg.edge.interaction_effect || "additive";
    eg.lineMat.opacity = effect === "cascading" ? 0.3 : effect === "amplifying" ? 0.2 : 0.12;
    eg.particles.forEach(p => { p.material.opacity = 0.6; });
  }
  for (const nm of nodeMeshes) {
    nm.mesh.material.opacity = 1.0;
    nm.mesh.material.transparent = false;
    nm.glow.material.opacity = 0.08;
  }
  closeDetailPanel();
}

function zoomToNode(mesh) {
  const target = mesh.position.clone();
  const camPos = target.clone().add(new THREE.Vector3(5, 8, 10));
  animateCamera(camPos, target);
}

function animateCamera(toPos, toTarget) {
  const fromPos = camera.position.clone();
  const fromTarget = controls.target.clone();
  const duration = 800;
  const start = performance.now();

  function step(now) {
    const t = Math.min((now - start) / duration, 1);
    const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    camera.position.lerpVectors(fromPos, toPos, ease);
    controls.target.lerpVectors(fromTarget, toTarget, ease);
    controls.update();
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ── Tooltip ──────────────────────────────────────────────────────────────────

function showTooltip(x, y, clause) {
  const exposure = clause.economics?.adjusted_exposure || 0;
  const exposureStr = "$" + exposure.toLocaleString();
  tooltip.innerHTML = `
    <div class="tt-title">${clause.title}</div>
    <div class="tt-family">${clause.family.replace(/_/g, " ")}</div>
    <div class="tt-risk">Risk: ${"&#9679;".repeat(clause.risk_rating)}${"&#9675;".repeat(5 - clause.risk_rating)}</div>
    <div class="tt-exposure">${exposureStr}</div>
  `;
  tooltip.style.display = "block";
  tooltip.style.left = (x + 16) + "px";
  tooltip.style.top = (y - 10) + "px";
}

function hideTooltip() {
  tooltip.style.display = "none";
}

// ── Detail Panel ─────────────────────────────────────────────────────────────

function showDetailPanel(clause) {
  layout.classList.add("detail-open");
  detailTitle.textContent = `${clause.number}. ${clause.title}`;

  const econ = clause.economics || {};
  const mc = econ.monte_carlo || {};
  const recs = clause.recommendations || [];
  const maxMC = mc.p5 || 1;

  let html = "";

  // Plain English
  html += `
    <div class="detail-section">
      <p class="ds-label">What This Means</p>
      <p class="ds-text">${clause.plain_english || ""}</p>
    </div>`;

  // What matters / watch for
  if (clause.what_matters) {
    html += `
    <div class="detail-section">
      <p class="ds-label">Why It Matters</p>
      <p class="ds-text">${clause.what_matters}</p>
      <p class="ds-label" style="margin-top:6px">Watch For</p>
      <p class="ds-text" style="color:#f59e0b">${clause.watch_for || ""}</p>
    </div>`;
  }

  // Actors
  html += `
    <div class="detail-section">
      <p class="ds-label">Actors</p>
      <div class="actor-badges">
        ${(clause.actors || []).map(a => `<span class="actor-badge ${a}">${a}</span>`).join("")}
      </div>
    </div>`;

  // Risk bar
  const riskPct = (clause.risk_rating / 5) * 100;
  const riskColor = clause.risk_rating >= 4 ? "#ef4444" : clause.risk_rating >= 3 ? "#f59e0b" : "#10b981";
  html += `
    <div class="detail-section">
      <p class="ds-label">Risk Rating: ${clause.risk_rating}/5</p>
      <div class="risk-bar-wrap">
        <div class="risk-bar"><div class="risk-bar-fill" style="width:${riskPct}%; background:${riskColor}"></div></div>
      </div>
    </div>`;

  // Economics
  html += `
    <div class="detail-section">
      <p class="ds-label">Financial Exposure</p>
      <div class="econ-grid">
        <div class="econ-card">
          <div class="econ-card-label">Base Exposure</div>
          <div class="econ-card-value money">$${(econ.exposure_base || 0).toLocaleString()}</div>
        </div>
        <div class="econ-card">
          <div class="econ-card-label">Adjusted</div>
          <div class="econ-card-value money">$${(econ.adjusted_exposure || 0).toLocaleString()}</div>
        </div>
        <div class="econ-card">
          <div class="econ-card-label">Interaction Mult.</div>
          <div class="econ-card-value">${(econ.interaction_multiplier || 1).toFixed(1)}x</div>
        </div>
        <div class="econ-card">
          <div class="econ-card-label">Cash Days</div>
          <div class="econ-card-value">${econ.cash_impact_days || 0}d</div>
        </div>
      </div>
    </div>`;

  // Monte Carlo
  if (mc.ev) {
    html += `
    <div class="detail-section">
      <p class="ds-label">Monte Carlo Distribution</p>
      ${mcBar("P5", mc.p5, maxMC, "#ef4444")}
      ${mcBar("P10", mc.p10, maxMC, "#f59e0b")}
      ${mcBar("EV", mc.ev, maxMC, "#3b82f6")}
      ${mcBar("P90", mc.p90, maxMC, "#10b981")}
    </div>`;
  }

  // Obligations
  if (clause.obligations?.length) {
    html += `
    <div class="detail-section">
      <p class="ds-label">Obligations</p>
      ${clause.obligations.slice(0, 5).map(o => `
        <div class="obl-row">
          <span class="obl-type ${o.type}">${o.type}</span>
          <span class="obl-text"><strong>${o.actor}:</strong> ${o.verb}</span>
        </div>
      `).join("")}
    </div>`;
  }

  // Recommendations
  if (recs.length) {
    html += `
    <div class="detail-section">
      <p class="ds-label">Recommendations</p>
      ${recs.map(r => `
        <div class="detail-rec">
          <div class="detail-rec-action">${r.action}</div>
          <div class="detail-rec-meta">
            <span class="detail-rec-impact">+$${(r.impact_cash || 0).toLocaleString()}</span>
            <span class="detail-rec-impact">+${r.impact_margin_pct || 0}% margin</span>
            <span class="detail-rec-effort">${r.effort} effort</span>
            <span style="color:#f59e0b;font-weight:700">${r.priority_score}/10</span>
          </div>
        </div>
      `).join("")}
    </div>`;
  }

  // Ambiguity flags
  if (clause.ambiguity_flags?.length) {
    html += `
    <div class="detail-section">
      <p class="ds-label">Ambiguity Flags</p>
      ${clause.ambiguity_flags.map(f => `<div class="ambiguity-flag">${f}</div>`).join("")}
    </div>`;
  }

  // Source text
  html += `
    <div class="detail-section">
      <p class="ds-label">Source Text</p>
      <div class="ds-source">${clause.source_text || ""}</div>
    </div>`;

  // Confidence + audit
  html += `
    <div class="detail-section">
      <p class="ds-label">Confidence</p>
      <div class="confidence-bar">
        <div class="confidence-fill"><div class="confidence-fill-inner" style="width:${(clause.confidence || 0) * 100}%"></div></div>
        <span>${((clause.confidence || 0) * 100).toFixed(0)}%</span>
      </div>
      <p class="ds-label" style="margin-top:8px">Audit Trail</p>
      <div class="audit-trail">${(clause.audit_trail || []).join("<br>")}</div>
    </div>`;

  detailBody.innerHTML = html;
  setTimeout(resize, 350); // Resize after CSS transition
}

function mcBar(label, value, max, color) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return `
    <div class="mc-bar-wrap">
      <span class="mc-bar-label">${label}</span>
      <div class="mc-bar"><div class="mc-bar-fill" style="width:${pct}%;background:${color}"></div></div>
      <span class="mc-bar-value">$${(value || 0).toLocaleString()}</span>
    </div>`;
}

function closeDetailPanel() {
  layout.classList.remove("detail-open");
  setTimeout(resize, 350);
}

// ── Role filtering ───────────────────────────────────────────────────────────

function applyRoleFilter() {
  const checks = document.querySelectorAll(".role-check input");
  const active = new Set();
  checks.forEach(c => { if (c.checked) active.add(c.value); });

  for (const nm of nodeMeshes) {
    const actors = nm.clause.actors || ["both"];
    const visible = actors.some(a => active.has(a));
    nm.mesh.visible = visible;
    nm.glow.visible = visible;
  }
}

// ── View mode toggle ─────────────────────────────────────────────────────────

function applyViewMode() {
  for (const nm of nodeMeshes) {
    if (viewMode === "economics") {
      // Size by financial exposure
      const exposure = nm.clause.economics?.adjusted_exposure || 0;
      const maxExposure = 40000000;
      const scale = 0.5 + Math.min(exposure / maxExposure, 1) * 2.5;
      nm.mesh.scale.setScalar(scale);
      nm.glow.scale.setScalar(scale);

      // Color by exposure level
      const ratio = Math.min(exposure / maxExposure, 1);
      const color = new THREE.Color().lerpColors(
        new THREE.Color(0x10b981), new THREE.Color(0xef4444), ratio
      );
      nm.mesh.material.color = color;
      nm.mesh.material.emissive = color;
    } else {
      // Size by risk
      nm.mesh.scale.setScalar(1.0);
      nm.glow.scale.setScalar(1.0);
      nm.mesh.material.color = new THREE.Color(nm.zoneColor);
      nm.mesh.material.emissive = new THREE.Color(nm.zoneColor);
    }
  }
}

// ── Scenario playback ────────────────────────────────────────────────────────

async function runScenario(scenarioId) {
  if (scenarioRunning) return;
  scenarioRunning = true;

  const resp = await fetch(`/contracttwin/scenarios/${scenarioId}`);
  const data = await resp.json();
  if (data.error) {
    scenarioRunning = false;
    return;
  }

  const timeline = document.getElementById("scenarioTimeline");
  const progress = document.getElementById("timelineProgress");
  const label    = document.getElementById("timelineLabel");
  const cost     = document.getElementById("timelineCost");
  timeline.style.display = "block";

  // Show scenario result in sidebar
  const resultDiv = document.getElementById("scenarioResult");
  resultDiv.style.display = "block";
  resultDiv.innerHTML = `
    <div><span class="sr-label">Scenario:</span> ${data.scenario.name}</div>
    <div><span class="sr-label">Severity:</span> <span class="sr-severity-${data.scenario.severity}">${data.scenario.severity}</span></div>
    <div><span class="sr-label">Total EV:</span> <span class="sr-value">$${data.total_ev.toLocaleString()}</span></div>
  `;

  deselectAll();

  const activations = data.activations;
  const totalSteps = activations.length;

  for (let i = 0; i < totalSteps; i++) {
    const act = activations[i];
    const pct = ((i + 1) / totalSteps) * 100;
    progress.style.width = pct + "%";
    label.textContent = act.effect;
    cost.textContent = `Cumulative: $${act.cumulative_exposure.toLocaleString()} (EV: $${act.cumulative_ev.toLocaleString()})`;

    // Highlight the activated clause
    if (act.clause_id) {
      const nm = nodeMeshes.find(n => n.clause.id === act.clause_id);
      if (nm) {
        pulseNode(nm, 0xef4444);
      }
    }

    await sleep(act.delay_ms || 500);
  }

  // Keep timeline visible for review
  setTimeout(() => {
    timeline.style.display = "none";
    scenarioRunning = false;
    deselectAll();
  }, 4000);
}

function pulseNode(nm, color) {
  const origColor = nm.mesh.material.color.clone();
  const origEmissive = nm.mesh.material.emissiveIntensity;

  nm.mesh.material.color.set(color);
  nm.mesh.material.emissiveIntensity = 0.8;
  nm.glow.material.color.set(color);
  nm.glow.material.opacity = 0.3;
  nm.mesh.scale.setScalar(1.8);

  setTimeout(() => {
    nm.mesh.material.color.copy(origColor);
    nm.mesh.material.emissiveIntensity = origEmissive;
    nm.glow.material.color.set(nm.zoneColor);
    nm.glow.material.opacity = 0.08;
    nm.mesh.scale.setScalar(1.0);
  }, 2000);
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ── Animation loop ───────────────────────────────────────────────────────────

function animate() {
  requestAnimationFrame(animate);
  animFrame++;
  controls.update();

  // Animate edge particles
  for (const eg of edgeGroups) {
    for (const p of eg.particles) {
      p.userData.t += p.userData.speed;
      if (p.userData.t > 1) p.userData.t -= 1;
      const pt = eg.curve.getPoint(p.userData.t);
      p.position.copy(pt);
    }
  }

  // Gentle zone pulse
  if (animFrame % 2 === 0) {
    const t = Date.now() * 0.001;
    for (const [name, group] of Object.entries(zoneGroups)) {
      const s = 1.0 + Math.sin(t + name.length) * 0.02;
      group.children[0].scale.set(s, 1, s);
    }
  }

  renderer.render(scene, camera);
}

// ── Data loading ─────────────────────────────────────────────────────────────

function renderContract(data) {
  contractData = data;

  // Clear existing
  for (const nm of nodeMeshes) {
    scene.remove(nm.mesh);
    scene.remove(nm.glow);
  }
  for (const eg of edgeGroups) {
    scene.remove(eg.group);
  }
  for (const g of Object.values(zoneGroups)) {
    scene.remove(g);
  }
  nodeMeshes = [];
  edgeGroups = [];
  zoneGroups = {};

  // Assign positions to clauses from graph nodes
  const posMap = {};
  for (const node of data.graph.nodes) {
    posMap[node.id] = node.position;
  }
  for (const clause of data.clauses) {
    clause._position = posMap[clause.id] || [0, 2, 0];
  }

  // Build scene
  createZones(data.zones);
  createNodes(data.clauses);
  createEdges(data.graph);

  // Update sidebar
  document.getElementById("contractInfo").style.display = "block";
  document.getElementById("viewControls").style.display = "block";
  document.getElementById("scenarioSection").style.display = "block";
  document.getElementById("zoneLegend").style.display = "block";
  document.getElementById("topRecsSection").style.display = "block";

  document.getElementById("contractTitle").textContent = data.title || "Contract";
  document.getElementById("statClauses").textContent = data.clauses.length;
  document.getElementById("statEdges").textContent = data.graph.edges.length;

  const portfolio = data.portfolio_summary || {};
  document.getElementById("statExposure").textContent =
    "$" + (portfolio.total_exposure || 0).toLocaleString();
  const margin = ((portfolio.risk_adjusted_margin || 0) * 100).toFixed(1);
  document.getElementById("statMargin").textContent = margin + "%";

  // Zone legend
  const legendItems = document.getElementById("legendItems");
  legendItems.innerHTML = "";
  for (const [name, config] of Object.entries(data.zones)) {
    const item = document.createElement("div");
    item.className = "legend-item";
    item.innerHTML = `<span class="legend-dot" style="background:${config.color}"></span>${config.label}`;
    item.addEventListener("click", () => {
      const pos = config.position;
      animateCamera(
        new THREE.Vector3(pos[0] + 5, 12, pos[2] + 10),
        new THREE.Vector3(pos[0], 2, pos[2])
      );
    });
    legendItems.appendChild(item);
  }

  // Scenarios
  scenarioSelect.innerHTML = '<option value="">Select scenario...</option>';
  for (const s of data.scenarios || []) {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = `${s.name} (EV: $${s.total_ev.toLocaleString()})`;
    scenarioSelect.appendChild(opt);
  }

  // Top recommendations
  const topRecs = portfolio.highest_roi_fixes || [];
  const recsDiv = document.getElementById("topRecsList");
  recsDiv.innerHTML = topRecs.slice(0, 5).map(r => `
    <div class="rec-card">
      <div class="rec-action">${r.action}</div>
      <div><span class="rec-impact">+$${(r.impact_cash || 0).toLocaleString()}</span>
      <span class="rec-priority">${r.priority_score}/10</span></div>
    </div>
  `).join("");

  loadingOverlay.style.display = "none";
}

async function loadDemo() {
  loadingOverlay.style.display = "flex";
  try {
    const resp = await fetch("/contracttwin/demo");
    const data = await resp.json();
    renderContract(data);
  } catch (err) {
    console.error("Failed to load demo:", err);
    loadingOverlay.style.display = "none";
  }
}

async function parseContract() {
  const text = contractInput.value.trim();
  if (!text || text.length < 100) return;
  loadingOverlay.style.display = "flex";
  try {
    const resp = await fetch("/contracttwin/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await resp.json();
    if (data.error) {
      alert(data.error);
      loadingOverlay.style.display = "none";
      return;
    }
    renderContract(data);
  } catch (err) {
    console.error("Failed to parse:", err);
    loadingOverlay.style.display = "none";
  }
}

// ── Event listeners ──────────────────────────────────────────────────────────

loadDemoBtn.addEventListener("click", loadDemo);
parseBtn.addEventListener("click", parseContract);
detailClose.addEventListener("click", () => {
  deselectAll();
});

runScenarioBtn.addEventListener("click", () => {
  const id = scenarioSelect.value;
  if (id) runScenario(id);
});

// View mode toggle
document.querySelectorAll(".toggle-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".toggle-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    viewMode = btn.dataset.view;
    applyViewMode();
  });
});

// Role filters
document.querySelectorAll(".role-check input").forEach(check => {
  check.addEventListener("change", applyRoleFilter);
});

// ── Startup ──────────────────────────────────────────────────────────────────

initScene();
animate();
