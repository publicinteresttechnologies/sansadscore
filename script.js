const rankingsEl = document.getElementById("rankings");
const searchInput = document.getElementById("searchInput");
const lastUpdatedEl = document.getElementById("lastUpdated");

let allMps = [];
let allSourceRecords = [];

const metricWeights = {
  "Constituency Focus": 0.25,
  "Parliamentary Work": 0.25,
  "Promise Follow-Through": 0.25,
  "Public Value": 0.15,
  "Trust & Evidence": 0.10
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

function calculateOverallScore(mp) {
  if (typeof mp.score === "number") {
    return Math.round(mp.score);
  }

  if (!mp.variables) {
    return 0;
  }

  return Math.round(
    Object.entries(metricWeights).reduce((total, [metric, weight]) => {
      return total + (safeNumber(mp.variables[metric]) * weight);
    }, 0)
  );
}

function scoreRow(label, value) {
  const safeValue = Math.max(0, Math.min(100, safeNumber(value)));

  return `
    <div class="score-row">
      <span>${escapeHtml(label)}</span>
      <div class="bar">
        <div class="fill" style="width: ${safeValue}%"></div>
      </div>
      <strong>${safeValue}</strong>
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
  const registeredInterests = rawValue(mp, "registered_interests_count");
  const manualRecords = rawValue(mp, "manual_source_records_count");

  const promiseRecords = countRecordsByType(records, ["promise", "pledge", "manifesto"]);
  const actionRecords = countRecordsByType(records, ["action", "question", "debate", "campaign", "meeting", "letter"]);
  const outcomeRecords = countRecordsByType(records, ["outcome", "delivery", "result", "completed", "approved", "funded"]);
  const publicValueRecords = countRecordsByType(records, ["cost", "value", "ipsa", "expense", "funding", "public_value"]);
  const trustRecords = countRecordsByType(records, ["trust", "interest", "register"]);
  const parliamentRecords = countRecordsBySource(records, ["parliament"]);
  const mediaRecords = countRecordsBySource(records, ["news", "media", "local_news"]);
  const officialRecords = countRecordsBySource(records, ["official", "government", "council", "nhs", "transport", "regulator"]);

  return `
    <div class="metric-explain">
      <h4>Why this score?</h4>

      <div class="metric-explain-grid">
        <div>
          <strong>Constituency Focus</strong>
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
          <strong>Promise Follow-Through</strong>
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
            IPSA/expense/funding signals are treated as evidence, not automatic praise or blame.
          </p>
        </div>

        <div>
          <strong>Trust & Evidence</strong>
          <p>
            Registered-interest records: ${registeredInterests}. 
            Trust records: ${trustRecords}. 
            Official records: ${officialRecords}. 
            Media records: ${mediaRecords}. 
            Manual/source records: ${manualRecords}.
          </p>
        </div>
      </div>
    </div>
  `;
}

function sourceRecordLabel(record) {
  const type = escapeHtml(record.type || record.record_type || "source");
  const sourceType = escapeHtml(record.source_type || record.evidence_type || record.source_connector || "source");
  const score = record.score !== undefined ? ` · evidence ${escapeHtml(record.score)}` : "";

  return `${type} · ${sourceType}${score}`;
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
      <summary>Why this score?</summary>
      ${buildRawEvidence(mp)}
      ${buildMetricExplanation(mp, records)}
      ${buildSourceLinks(records)}
    </details>
  `;
}

function render(mps) {
  rankingsEl.innerHTML = mps.map(mp => {
    const overallScore = calculateOverallScore(mp);
    const records = getRecordsForMp(mp);

    const legalFlag = mp.legal_flag
      ? `<div class="flag">${escapeHtml(mp.legal_flag)}</div>`
      : "";

    const photoBlock = mp.photo_url
      ? `<img class="photo" src="${escapeHtml(mp.photo_url)}" alt="">`
      : `<div class="photo placeholder">${escapeHtml(getInitials(mp.name))}</div>`;

    const variableRows = Object.entries(mp.variables || {})
      .map(([label, value]) => scoreRow(label, value))
      .join("");

    return `
      <article class="card">
        <div class="card-top">
          <div class="rank">#${escapeHtml(mp.rank)}</div>

          ${photoBlock}

          <div class="identity">
            <h2>${escapeHtml(mp.name)}</h2>
            <p>${escapeHtml(mp.constituency)} | ${escapeHtml(mp.party)}</p>
            <p class="overall-score">Overall Score: ${overallScore}/100</p>
          </div>

          <div class="grade">${escapeHtml(mp.grade)}</div>
        </div>

        ${legalFlag}

        <div class="scores">
          ${variableRows}
        </div>

        <div class="verdict">
          ${escapeHtml(mp.verdict || "")}
        </div>

        ${buildEvidencePanel(mp, records)}

        <div class="actions">
          <a href="${escapeHtml(mp.source_url || "#")}" target="_blank" rel="noopener">Sources</a>
          <button onclick="shareCard(${Number(mp.rank)})">Share</button>
        </div>
      </article>
    `;
  }).join("");
}

function shareCard(rank) {
  const mp = allMps.find(item => Number(item.rank) === Number(rank));

  if (!mp) return;

  const overallScore = calculateOverallScore(mp);

  const text = `Commons Score: #${mp.rank} ${mp.name} — ${overallScore}/100 — Grade ${mp.grade}`;

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
      mp.grade,
      mp.verdict
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

  allMps = data.mps || [];
  allSourceRecords = await loadSourceRecords();

  lastUpdatedEl.textContent = `Last updated: ${data.last_updated}`;

  render(allMps);
}

searchInput.addEventListener("input", filterMps);

loadData();
