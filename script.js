const rankingsEl = document.getElementById("rankings");
const searchInput = document.getElementById("searchInput");
const lastUpdatedEl = document.getElementById("lastUpdated");

const METRICS = ["Activity", "Local Focus", "Delivery", "Public Value", "Proof"];
let allMps = [];
let displayedMps = [];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function clampScore(value) {
  return Math.max(0, Math.min(100, safeNumber(value)));
}

function formatScore(value) {
  return clampScore(value).toLocaleString("en-GB", { maximumFractionDigits: 2 });
}

function formatMetric(value) {
  return clampScore(value).toLocaleString("en-GB", { maximumFractionDigits: 1 });
}

function getMemberId(mp) {
  return mp?.raw?.member_id || mp?.member_id || mp?.id || null;
}

function getContactUrl(mp) {
  const direct = mp.boost_url || mp.source_url;
  if (direct && String(direct).startsWith("http")) return direct;
  const memberId = getMemberId(mp);
  return memberId ? `https://members.parliament.uk/member/${encodeURIComponent(memberId)}/contact` : "https://members.parliament.uk/members/commons";
}

function getOverallScore(mp) {
  return clampScore(mp.final_score ?? mp.raw?.final_score ?? mp.score);
}

function getVariable(mp, keys) {
  const variables = mp.variables || {};
  for (const key of keys) if (variables[key] !== undefined) return clampScore(variables[key]);
  return 0;
}

function proofFallback(mp) {
  const raw = mp.raw || {};
  const official = safeNumber(raw.official_source_records_count) + safeNumber(raw.parliament_source_records_count);
  const completeness = clampScore(raw.data_completeness_score);
  const diversity = Math.min(100, safeNumber(raw.source_diversity_count) * 25);
  const volume = Math.min(100, official * 5);
  const strength = clampScore(raw.evidence_strength_average);
  return clampScore((completeness * 0.35) + (diversity * 0.20) + (volume * 0.25) + (strength * 0.20));
}

function getMetricValue(mp, label) {
  if (mp.public_metrics && mp.public_metrics[label] !== undefined) return clampScore(mp.public_metrics[label]);
  if (label === "Activity") return getVariable(mp, ["Parliamentary Work"]);
  if (label === "Local Focus") return getVariable(mp, ["Constituency Work", "Constituency Focus"]);
  if (label === "Delivery") return getVariable(mp, ["Delivery Track", "Promise Follow-Through"]);
  if (label === "Public Value") return getVariable(mp, ["Public Value"]);
  if (label === "Proof") return proofFallback(mp);
  return 0;
}

function metricRow(mp, label) {
  const value = getMetricValue(mp, label);
  return `<div class="score-row"><div class="score-label"><span>${escapeHtml(label)}</span><strong>${formatMetric(value)}</strong></div><div class="bar"><div class="fill" style="width:${value}%"></div></div></div>`;
}

function initials(name) {
  return String(name || "").split(" ").filter(Boolean).map(part => part[0]).join("").slice(0, 2).toUpperCase();
}

function detailRow(label, value) {
  return `<div class="compact-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? "n/a")}</strong></div>`;
}

function sourceList(records) {
  if (!records.length) return `<div class="source-empty">No matched source records.</div>`;
  return `<ul class="source-list">${records.map(record => {
    const url = record.source_url || record.endpoint_or_url || "";
    const summary = escapeHtml(record.summary || record.source_name || "Source record");
    const label = escapeHtml(record.source_connector || record.source_type || record.type || "source");
    const title = String(url).startsWith("http") ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${summary}</a>` : `<span>${summary}</span>`;
    return `<li>${title}<small>${label}</small></li>`;
  }).join("")}</ul>`;
}

function auditList(entries) {
  if (!entries.length) return `<div class="source-empty">No source audit entries available.</div>`;
  return `<ul class="source-list">${entries.map(entry => `<li><span>${escapeHtml(entry.source_name || entry.connector || "source")}</span><small>${escapeHtml(entry.status || "status")} / ${safeNumber(entry.records_found)} found</small></li>`).join("")}</ul>`;
}

async function fetchSourceShard(mp) {
  const memberId = getMemberId(mp);
  if (!memberId) return { missing: true, records: [], source_audit: [] };
  const response = await fetch(`data/sources/${encodeURIComponent(memberId)}.json`, { cache: "no-store" });
  if (response.status === 404) return { missing: true, records: [], source_audit: [] };
  if (!response.ok) throw new Error(`Source shard request failed: ${response.status}`);
  const payload = await response.json();
  return {
    missing: false,
    records: Array.isArray(payload.records) ? payload.records : [],
    source_audit: Array.isArray(payload.source_audit) ? payload.source_audit : [],
  };
}

async function renderSourcesForCard(index) {
  const mp = displayedMps[index];
  const target = document.querySelector(`[data-source-index="${index}"]`);
  if (!mp || !target || target.dataset.loaded === "true" || target.dataset.loaded === "loading") return;
  target.dataset.loaded = "loading";
  target.innerHTML = `<div class="source-empty">Loading sources & methods...</div>`;
  try {
    const payload = await fetchSourceShard(mp);
    target.dataset.loaded = "true";
    target.innerHTML = `<div class="why-grid"><div class="score-accordion"><summary>Method</summary><div class="accordion-body">${detailRow("Score", `${formatScore(getOverallScore(mp))} / 100`)}${detailRow("Role", mp.role || mp.raw?.role_peer_group || "Standard MP")}${detailRow("Peer table", mp.rank_within_role_peer_group && mp.role_peer_group_size ? `${mp.rank_within_role_peer_group}/${mp.role_peer_group_size}` : "n/a")}${detailRow("Official records", mp.raw?.official_source_records_count ?? 0)}${detailRow("Parliament records", mp.raw?.parliament_source_records_count ?? 0)}</div></div><div class="source-evidence"><h4>Matched records</h4>${payload.missing ? `<div class="source-empty">No source shard is available for this MP yet.</div>` : sourceList(payload.records)}</div><div class="source-audit"><h4>Sources considered</h4>${payload.missing ? `<div class="source-empty">No source audit shard is available for this MP yet.</div>` : auditList(payload.source_audit)}</div></div>`;
  } catch (error) {
    target.dataset.loaded = "";
    target.innerHTML = `<div class="source-empty">Could not load sources & methods.</div><button type="button" class="load-sources" onclick="renderSourcesForCard(${index})">Try again</button>`;
  }
}

function render(mps) {
  displayedMps = [...mps].sort((a, b) => getOverallScore(b) - getOverallScore(a) || String(a.name || "").localeCompare(String(b.name || "")));
  rankingsEl.innerHTML = displayedMps.map((mp, index) => {
    const rank = index + 1;
    const photo = mp.photo_url ? `<img class="photo" src="${escapeHtml(mp.photo_url)}" alt="">` : `<div class="photo placeholder">${escapeHtml(initials(mp.name))}</div>`;
    return `<article class="card"><div class="card-topline"><span class="card-rank">#${rank}</span><span class="kicker">${escapeHtml(mp.constituency || "")}</span></div><div class="card-main"><div class="portrait-wrap">${photo}</div><div class="identity"><h2>${escapeHtml(mp.name)}</h2><p>${escapeHtml(mp.party || "Independent")}</p></div><div class="hero-score"><span>${formatScore(getOverallScore(mp))} / 100</span><a class="boost-action" href="${escapeHtml(getContactUrl(mp))}" target="_blank" rel="noopener">Boost your MP's rating</a></div></div><div class="chip-strip"><span><b>Role</b> ${escapeHtml(mp.role || mp.raw?.role_peer_group || "Standard MP")}</span><span><b>Party</b> ${escapeHtml(mp.party || "Independent")}</span></div><div class="scores">${METRICS.map(label => metricRow(mp, label)).join("")}</div><details class="why-panel"><summary>Sources & Methods</summary><div class="lazy-sources" data-source-index="${index}"><button type="button" class="load-sources" onclick="renderSourcesForCard(${index})">Load sources & methods</button></div></details></article>`;
  }).join("");
}

function filterMps() {
  const query = searchInput.value.toLowerCase();
  render(allMps.filter(mp => [mp.name, mp.constituency, mp.party, mp.role].join(" ").toLowerCase().includes(query)));
}

async function loadData() {
  const response = await fetch("data/ranked_mps.json", { cache: "no-store" });
  const data = await response.json();
  allMps = data.mps || [];
  lastUpdatedEl.textContent = `Last updated: ${data.last_updated || "unknown"}`;
  render(allMps);
}

searchInput.addEventListener("input", filterMps);
loadData();
