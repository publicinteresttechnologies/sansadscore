const rankingsEl = document.getElementById("rankings");
const searchInput = document.getElementById("searchInput");
const lastUpdatedEl = document.getElementById("lastUpdated");

let allMps = [];
let displayedMps = [];
let allSourceRecords = [];
let allSourceAudit = [];

const visibleMetrics = [
  {
    label: "Constituency Work",
    weight: 0.30,
    keys: ["Constituency Work", "Constituency Focus"]
  },
  {
    label: "Parliamentary Work",
    weight: 0.30,
    keys: ["Parliamentary Work"]
  },
  {
    label: "Delivery Track",
    weight: 0.25,
    keys: ["Delivery Track", "Promise Follow-Through"]
  },
  {
    label: "Public Value",
    weight: 0.15,
    keys: ["Public Value"]
  }
];

const auditSections = [
  { title: "Used in score", statuses: ["used_in_score"] },
  { title: "Diagnostic only", statuses: ["diagnostic_only"] },
  { title: "Context only", statuses: ["context_only"] },
  { title: "Discovery only", statuses: ["discovery_only"] },
  { title: "Considered but no match", statuses: ["no_match"] },
  { title: "Skipped in fast mode", statuses: ["skipped_fast_mode"] },
  { title: "Failed / TODO", statuses: ["failed", "todo_not_implemented"] }
];

const issueCategoryLabels = {
  health: "Health",
  crime_policing: "Crime and policing",
  housing: "Housing",
  transport: "Transport",
  flooding_environment: "Flooding and environment",
  sewage_water: "Sewage and water",
  education: "Education",
  employment_income: "Employment and income",
  planning_development: "Planning and development"
};

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

function rawOrTopLevel(mp, key, fallback = undefined) {
  if (mp?.raw && mp.raw[key] !== undefined && mp.raw[key] !== null) {
    return mp.raw[key];
  }

  if (mp && mp[key] !== undefined && mp[key] !== null) {
    return mp[key];
  }

  return fallback;
}

function getMetricValue(mp, metric) {
  const variables = mp.variables || {};

  for (const key of metric.keys) {
    if (variables[key] !== undefined) {
      return clampScore(variables[key]);
    }
  }

  return 0;
}

function calculateLegacyVisibleScore(mp) {
  return visibleMetrics.reduce((total, metric) => {
    return total + (getMetricValue(mp, metric) * metric.weight);
  }, 0);
}

function calculateOverallScore(mp) {
  const finalScore = rawOrTopLevel(mp, "final_score", mp?.score);

  if (finalScore !== undefined && finalScore !== null) {
    return clampScore(finalScore);
  }

  return calculateLegacyVisibleScore(mp);
}

function formatScore(value) {
  return clampScore(value).toLocaleString("en-GB", {
    maximumFractionDigits: 2
  });
}

function formatMultiplier(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "0.00";
  return number.toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function sortedByVisibleScore(mps) {
  return [...mps].sort((a, b) => {
    const scoreDifference = calculateOverallScore(b) - calculateOverallScore(a);

    if (scoreDifference !== 0) {
      return scoreDifference;
    }

    return String(a.name || "").localeCompare(String(b.name || ""));
  });
}

function scoreRow(label, value) {
  const safeValue = clampScore(value);

  return `
    <div class="score-row">
      <div class="score-label">
        <span>${escapeHtml(label)}</span>
        <strong>${formatScore(safeValue)}</strong>
      </div>
      <div class="bar">
        <div class="fill" style="width: ${safeValue}%"></div>
      </div>
    </div>
  `;
}

function getInitials(name) {
  return String(name || "")
    .split(" ")
    .filter(Boolean)
    .map(part => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function getMemberId(mp) {
  return (
    mp?.raw?.member_id ||
    mp?.member_id ||
    mp?.id ||
    null
  );
}

function normalize(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

function matchesMp(item, mp) {
  const memberId = getMemberId(mp);
  const name = normalize(mp.name);
  const constituency = normalize(mp.constituency);
  const itemMemberId = item.member_id || item.mp_id || null;
  const itemName = normalize(item.mp_name || item.name);
  const itemConstituency = normalize(item.constituency);

  if (memberId && itemMemberId && String(memberId) === String(itemMemberId)) {
    return true;
  }

  if (name && itemName && name === itemName) {
    return true;
  }

  if (constituency && itemConstituency && constituency === itemConstituency) {
    return true;
  }

  return false;
}

function getRecordsForMp(mp) {
  return allSourceRecords.filter(record => matchesMp(record, mp));
}

function getAuditForMp(mp) {
  return allSourceAudit.filter(entry => matchesMp(entry, mp));
}

function countRecordsByType(records, typeList) {
  const types = typeList.map(type => type.toLowerCase());

  return records.filter(record => {
    const type = normalize(record.type || record.record_type || record.category);
    return types.some(target => type.includes(target));
  }).length;
}

function countRecordsBySource(records, sourceList) {
  const sources = sourceList.map(source => source.toLowerCase());

  return records.filter(record => {
    const source = normalize(record.source_type || record.evidence_type || record.source_connector);
    return sources.some(target => source.includes(target));
  }).length;
}

function rawValue(mp, key) {
  return safeNumber(mp?.raw?.[key]);
}

function formatCategories(categories) {
  if (!Array.isArray(categories) || !categories.length) {
    return "None identified";
  }

  return categories
    .map(category => issueCategoryLabels[category] || category)
    .map(escapeHtml)
    .join(", ");
}

function calculationRow(label, value, options = {}) {
  const display = options.multiplier ? formatMultiplier(value) : `${formatScore(value)} / 100`;

  return `
    <div class="calc-row">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(display)}</strong>
    </div>
  `;
}

function buildCalculationBreakdown(mp) {
  const raw = mp.raw || {};
  const roleRank = raw.rank_within_role_peer_group && raw.role_peer_group_size
    ? `${raw.rank_within_role_peer_group} of ${raw.role_peer_group_size}`
    : "Not available";

  const notes = Array.isArray(raw.calculation_notes)
    ? raw.calculation_notes.map(note => `<li>${escapeHtml(note)}</li>`).join("")
    : "";

  return `
    <div class="calculation-breakdown">
      <h4>Calculation breakdown</h4>
      <p>
        Local conditions are not scored against an MP directly. They affect the score only by testing whether visible MP activity matches major constituency needs.
      </p>
      <div class="calc-grid">
        ${calculationRow("Base public score", raw.base_public_score ?? calculateLegacyVisibleScore(mp))}
        ${calculationRow("Evidence confidence multiplier", raw.evidence_confidence_multiplier ?? 1, { multiplier: true })}
        ${calculationRow("Confidence-adjusted score", raw.confidence_adjusted_score ?? calculateOverallScore(mp))}
        ${calculationRow("Role peer percentile", raw.role_peer_percentile ?? 50)}
        ${calculationRow("Role-adjusted score", raw.role_adjusted_score ?? calculateOverallScore(mp))}
        ${calculationRow("Need alignment score", raw.need_alignment_score ?? 50)}
        ${calculationRow("Final score", raw.final_score ?? calculateOverallScore(mp))}
      </div>
      <div class="calc-context">
        <span>${escapeHtml(raw.confidence_label || "Confidence not available")}</span>
        <span>${escapeHtml(raw.role_peer_group || mp.role || "Role peer group not available")}: ${escapeHtml(roleRank)}</span>
        <span>${escapeHtml(raw.need_alignment_label || "Need alignment not available")}</span>
      </div>
      ${notes ? `<ul class="calc-notes">${notes}</ul>` : ""}
    </div>
  `;
}

function buildMetricExplanation(mp, records) {
  const raw = mp.raw || {};
  const writtenQuestions = rawValue(mp, "written_questions_count");
  const localQuestions = rawValue(mp, "local_questions_count");
  const votes = rawValue(mp, "votes_count");
  const edms = rawValue(mp, "edms_count");
  const focusItems = rawValue(mp, "focus_items_count");

  const promiseRecords = countRecordsByType(records, ["promise", "pledge", "manifesto"]);
  const actionRecords = countRecordsByType(records, ["action", "question", "debate", "campaign", "meeting", "letter"]);
  const outcomeRecords = countRecordsByType(records, ["outcome", "delivery", "result", "completed", "approved", "funded"]);
  const publicValueRecords = countRecordsByType(records, ["cost", "value", "ipsa", "expense", "funding", "public_value"]);
  const parliamentRecords = countRecordsBySource(records, ["parliament"]);

  return `
    <div class="metric-explain">
      <h4>Score notes</h4>

      <div class="metric-explain-grid">
        <div>
          <strong>Constituency Work</strong>
          <p>
            Local written questions: ${localQuestions}.
            Focus items: ${focusItems}.
            Need alignment: ${formatScore(raw.need_alignment_score ?? 50)} / 100.
          </p>
        </div>

        <div>
          <strong>Parliamentary Work</strong>
          <p>
            Written questions: ${writtenQuestions}.
            Vote records: ${votes}.
            EDMs: ${edms}.
            Parliament source records: ${parliamentRecords}.
          </p>
        </div>

        <div>
          <strong>Delivery Track</strong>
          <p>
            Promise records: ${promiseRecords}.
            Action records: ${actionRecords}.
            Outcome/delivery records: ${outcomeRecords}.
            Verified delivery: ${formatScore(raw.verified_delivery_score ?? 0)} / 100.
          </p>
        </div>

        <div>
          <strong>Need Relevance</strong>
          <p>
            Constituency need categories: ${formatCategories(raw.constituency_need_categories)}.
            MP activity categories: ${formatCategories(raw.mp_activity_categories)}.
            Category matches: ${safeNumber(raw.category_alignment_count)}.
          </p>
        </div>

        <div>
          <strong>Public Value</strong>
          <p>
            Public-value/cost records: ${publicValueRecords}.
            IPSA/expense/funding signals are treated as public evidence, not automatic praise or blame.
          </p>
        </div>
      </div>
    </div>
  `;
}

function sourceRecordLabel(record) {
  const type = escapeHtml(record.type || record.record_type || "source");
  const sourceType = escapeHtml(record.source_type || record.evidence_type || record.source_connector || "source");
  const score = record.score !== undefined ? ` / evidence ${escapeHtml(record.score)}` : "";
  const issue = record.issue_category ? ` / ${escapeHtml(issueCategoryLabels[record.issue_category] || record.issue_category)}` : "";

  return `${type} / ${sourceType}${issue}${score}`;
}

function buildSourceLinks(records) {
  if (!records.length) {
    return `
      <div class="source-evidence">
        <h4>Matched source records</h4>
        <p>No matched source records for this MP yet.</p>
      </div>
    `;
  }

  const sorted = [...records].sort((a, b) => {
    return safeNumber(b.score) - safeNumber(a.score);
  });

  const topRecords = sorted.slice(0, 8);

  const list = topRecords.map(record => {
    const summary = escapeHtml(record.summary || "Source record");
    const url = escapeHtml(record.source_url || "#");
    const label = sourceRecordLabel(record);

    if (!record.source_url) {
      return `
        <li>
          <span>${summary}</span>
          <small>${label}</small>
        </li>
      `;
    }

    return `
      <li>
        <a href="${url}" target="_blank" rel="noopener">${summary}</a>
        <small>${label}</small>
      </li>
    `;
  }).join("");

  return `
    <div class="source-evidence">
      <h4>Matched source records</h4>
      <p>${records.length} source record(s) matched this MP. Showing strongest ${topRecords.length}.</p>
      <ul>${list}</ul>
    </div>
  `;
}

function auditDetail(entry) {
  const issue = entry.issue_category ? issueCategoryLabels[entry.issue_category] || entry.issue_category : "";
  const bits = [
    entry.source_name || entry.connector,
    entry.control_tier,
    issue,
    `${safeNumber(entry.records_found)} found`,
    entry.scored ? "scored" : "not scored",
    entry.run_mode ? `mode ${entry.run_mode}` : ""
  ].filter(Boolean);

  return bits.map(escapeHtml).join(" / ");
}

function buildAuditSection(title, entries) {
  if (!entries.length) {
    return `
      <div class="audit-section">
        <h5>${escapeHtml(title)}</h5>
        <p>No sources in this category.</p>
      </div>
    `;
  }

  const rows = entries.map(entry => {
    const url = entry.endpoint_or_url || "";
    const source = url.startsWith("http")
      ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(entry.source_name || entry.connector)}</a>`
      : `<span>${escapeHtml(entry.source_name || entry.connector)}</span>`;

    const error = entry.error ? `<em>Error: ${escapeHtml(entry.error)}</em>` : "";

    return `
      <li>
        ${source}
        <small>${auditDetail(entry)}</small>
        <p>${escapeHtml(entry.reason || "Source considered.")}</p>
        ${error}
      </li>
    `;
  }).join("");

  return `
    <div class="audit-section">
      <h5>${escapeHtml(title)}</h5>
      <ul>${rows}</ul>
    </div>
  `;
}

function buildSourceAudit(auditEntries) {
  if (!auditEntries.length) {
    return `
      <div class="source-audit">
        <h4>Full source audit</h4>
        <p>No source audit entries are available for this MP yet.</p>
      </div>
    `;
  }

  const sections = auditSections.map(section => {
    const entries = auditEntries.filter(entry => section.statuses.includes(entry.status));
    return buildAuditSection(section.title, entries);
  }).join("");

  return `
    <div class="source-audit">
      <h4>Full source audit</h4>
      ${sections}
    </div>
  `;
}

function buildRawEvidence(mp) {
  const raw = mp.raw || {};

  const rows = [
    ["Member ID", raw.member_id],
    ["Written questions", raw.written_questions_count],
    ["Local written questions", raw.local_questions_count],
    ["Vote records", raw.votes_count],
    ["EDMs", raw.edms_count],
    ["Focus items", raw.focus_items_count],
    ["Registered interests", raw.registered_interests_count],
    ["Manual/source records", raw.manual_source_records_count]
  ];

  const renderedRows = rows.map(([label, value]) => {
    return `
      <div class="raw-row">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value ?? 0)}</strong>
      </div>
    `;
  }).join("");

  return `
    <div class="raw-evidence">
      <h4>Raw evidence counts</h4>
      <div class="raw-grid">
        ${renderedRows}
      </div>
    </div>
  `;
}

function buildEvidencePanel(mp, records, auditEntries) {
  return `
    <details class="evidence-panel">
      <summary>Sources</summary>
      ${buildCalculationBreakdown(mp)}
      ${buildRawEvidence(mp)}
      ${buildMetricExplanation(mp, records)}
      ${buildSourceLinks(records)}
      ${buildSourceAudit(auditEntries)}
    </details>
  `;
}

function buildMetricRows(mp) {
  return visibleMetrics.map(metric => {
    return scoreRow(metric.label, getMetricValue(mp, metric));
  }).join("");
}

function buildContextStrip(mp) {
  const raw = mp.raw || {};
  const confidence = raw.confidence_label || mp.confidence_label || "Confidence pending";
  const roleGroup = raw.role_peer_group || mp.role_peer_group || mp.role || "Role pending";
  const roleRank = raw.rank_within_role_peer_group && raw.role_peer_group_size
    ? `#${raw.rank_within_role_peer_group} of ${raw.role_peer_group_size}`
    : "rank pending";
  const need = raw.need_alignment_label || mp.need_alignment_label || "Need alignment pending";

  return `
    <div class="context-strip">
      <span>${escapeHtml(confidence)}</span>
      <span>${escapeHtml(roleGroup)} / ${escapeHtml(roleRank)}</span>
      <span>${escapeHtml(need)}</span>
    </div>
  `;
}

function render(mps) {
  displayedMps = sortedByVisibleScore(mps);

  rankingsEl.innerHTML = displayedMps.map((mp, index) => {
    const rank = index + 1;
    const overallScore = calculateOverallScore(mp);
    const records = getRecordsForMp(mp);
    const auditEntries = getAuditForMp(mp);

    const legalFlag = mp.legal_flag
      ? `<div class="flag">${escapeHtml(mp.legal_flag)}</div>`
      : "";

    const photoBlock = mp.photo_url
      ? `<img class="photo" src="${escapeHtml(mp.photo_url)}" alt="">`
      : `<div class="photo placeholder">${escapeHtml(getInitials(mp.name))}</div>`;

    return `
      <article class="card">
        <div class="card-rank" aria-label="Rank ${rank}">${rank}</div>

        <div class="card-main">
          <div class="portrait-wrap">
            ${photoBlock}
          </div>

          <div class="identity">
            <p class="kicker">${escapeHtml(mp.party || "Independent")}</p>
            <h2>${escapeHtml(mp.name)}</h2>
            <p>${escapeHtml(mp.constituency)}</p>
          </div>

          <div class="hero-score">
            <span>${formatScore(overallScore)} / 100</span>
          </div>
        </div>

        ${legalFlag}
        ${buildContextStrip(mp)}

        <div class="scores">
          ${buildMetricRows(mp)}
        </div>

        ${buildEvidencePanel(mp, records, auditEntries)}

        <div class="actions">
          <a href="${escapeHtml(mp.source_url || "#")}" target="_blank" rel="noopener">Sources</a>
          <button onclick="shareCard(${index})">Share</button>
        </div>
      </article>
    `;
  }).join("");
}

function shareCard(index) {
  const mp = displayedMps[index];

  if (!mp) return;

  const overallScore = calculateOverallScore(mp);
  const rank = index + 1;
  const text = `Commons Score: #${rank} ${mp.name} - ${formatScore(overallScore)} / 100`;

  if (navigator.share) {
    navigator.share({ text });
  } else {
    navigator.clipboard.writeText(text);
    alert("Copied share text.");
  }
}

function filterMps() {
  const query = searchInput.value.toLowerCase();

  const filtered = allMps.filter(mp => {
    return [
      mp.name,
      mp.constituency,
      mp.party,
      mp.role,
      rawOrTopLevel(mp, "role_peer_group", ""),
      rawOrTopLevel(mp, "confidence_label", ""),
      rawOrTopLevel(mp, "need_alignment_label", "")
    ].join(" ").toLowerCase().includes(query);
  });

  render(filtered);
}

async function loadSourceData() {
  try {
    const response = await fetch("data/source_records.json", { cache: "no-store" });

    if (!response.ok) {
      return { records: [], sourceAudit: [] };
    }

    const data = await response.json();

    if (Array.isArray(data)) {
      return { records: data, sourceAudit: [] };
    }

    return {
      records: Array.isArray(data.records) ? data.records : [],
      sourceAudit: Array.isArray(data.source_audit) ? data.source_audit : []
    };
  } catch (error) {
    return { records: [], sourceAudit: [] };
  }
}

async function loadData() {
  const response = await fetch("data/ranked_mps.json", { cache: "no-store" });
  const data = await response.json();
  const sourceData = await loadSourceData();

  allMps = sortedByVisibleScore(data.mps || []);
  allSourceRecords = sourceData.records;
  allSourceAudit = sourceData.sourceAudit;

  lastUpdatedEl.textContent = `Last updated: ${data.last_updated}`;

  render(allMps);
}

searchInput.addEventListener("input", filterMps);

loadData();
