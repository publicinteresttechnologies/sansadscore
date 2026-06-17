const rankingsEl = document.getElementById("rankings");
const searchInput = document.getElementById("searchInput");
const lastUpdatedEl = document.getElementById("lastUpdated");

let allMps = [];
let displayedMps = [];
let allSourceRecords = [];

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

function getMetricValue(mp, metric) {
  const variables = mp.variables || {};

  for (const key of metric.keys) {
    if (variables[key] !== undefined) {
      return clampScore(variables[key]);
    }
  }

  return 0;
}

function calculateOverallScore(mp) {
  return visibleMetrics.reduce((total, metric) => {
    return total + (getMetricValue(mp, metric) * metric.weight);
  }, 0);
}

function formatScore(value) {
  return clampScore(value).toLocaleString("en-GB", {
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

function getRecordsForMp(mp) {
  const memberId = getMemberId(mp);
  const name = normalize(mp.name);
  const constituency = normalize(mp.constituency);

  return allSourceRecords.filter(record => {
    const recordMemberId = record.member_id || record.mp_id || null;
    const recordName = normalize(record.mp_name || record.name);
    const recordConstituency = normalize(record.constituency);

    if (memberId && recordMemberId && String(memberId) === String(recordMemberId)) {
      return true;
    }

    if (name && recordName && name === recordName) {
      return true;
    }

    if (constituency && recordConstituency && constituency === recordConstituency) {
      return true;
    }

    return false;
  });
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

function buildMetricExplanation(mp, records) {
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
            Local action/source records: ${actionRecords + outcomeRecords}.
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

  return `${type} / ${sourceType}${score}`;
}

function buildSourceLinks(records) {
  if (!records.length) {
    return `
      <div class="source-evidence">
        <h4>Source evidence</h4>
        <p>No source records matched this MP yet.</p>
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
      <h4>Source evidence</h4>
      <p>${records.length} source record(s) matched this MP. Showing strongest ${topRecords.length}.</p>
      <ul>${list}</ul>
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

function buildEvidencePanel(mp, records) {
  return `
    <details class="evidence-panel">
      <summary>Score evidence</summary>
      ${buildRawEvidence(mp)}
      ${buildMetricExplanation(mp, records)}
      ${buildSourceLinks(records)}
    </details>
  `;
}

function buildMetricRows(mp) {
  return visibleMetrics.map(metric => {
    return scoreRow(metric.label, getMetricValue(mp, metric));
  }).join("");
}

function render(mps) {
  displayedMps = sortedByVisibleScore(mps);

  rankingsEl.innerHTML = displayedMps.map((mp, index) => {
    const rank = index + 1;
    const overallScore = calculateOverallScore(mp);
    const records = getRecordsForMp(mp);

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

        <div class="scores">
          ${buildMetricRows(mp)}
        </div>

        ${buildEvidencePanel(mp, records)}

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
      mp.role
    ].join(" ").toLowerCase().includes(query);
  });

  render(filtered);
}

async function loadSourceRecords() {
  try {
    const response = await fetch("data/source_records.json", { cache: "no-store" });

    if (!response.ok) {
      return [];
    }

    const data = await response.json();

    if (Array.isArray(data)) {
      return data;
    }

    if (Array.isArray(data.records)) {
      return data.records;
    }

    return [];
  } catch (error) {
    return [];
  }
}

async function loadData() {
  const response = await fetch("data/ranked_mps.json", { cache: "no-store" });
  const data = await response.json();

  allMps = sortedByVisibleScore(data.mps || []);
  allSourceRecords = await loadSourceRecords();

  lastUpdatedEl.textContent = `Last updated: ${data.last_updated}`;

  render(allMps);
}

searchInput.addEventListener("input", filterMps);

loadData();
