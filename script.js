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
  { title: "No match", statuses: ["no_match"] },
  { title: "Skipped / failed / TODO", statuses: ["skipped_fast_mode", "failed", "todo_not_implemented"] }
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

function dataValue(mp, key, fallback = undefined) {
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

function calculateMetricScore(mp) {
  return visibleMetrics.reduce((total, metric) => {
    return total + (getMetricValue(mp, metric) * metric.weight);
  }, 0);
}

function calculateOverallScore(mp) {
  const finalScore = dataValue(mp, "final_score", mp?.score);
  return finalScore !== undefined ? clampScore(finalScore) : calculateMetricScore(mp);
}

function formatScore(value) {
  return clampScore(value).toLocaleString("en-GB", {
    maximumFractionDigits: 2
  });
}

function formatMetric(value) {
  return clampScore(value).toLocaleString("en-GB", {
    maximumFractionDigits: 1
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
        <strong>${formatMetric(safeValue)}</strong>
      </div>
      <div class="bar" aria-hidden="true">
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

function compactLabel(value, fallback) {
  const text = String(value || fallback || "").trim();
  return text.length > 34 ? `${text.slice(0, 31)}...` : text;
}

function confidenceLabel(mp) {
  const explicit = dataValue(mp, "confidence_label");
  if (explicit) return String(explicit).replace(" confidence", "");

  const completeness = safeNumber(mp?.raw?.data_completeness_score);
  if (completeness >= 70) return "High";
  if (completeness > 0 && completeness < 40) return "Low";
  return "Medium";
}

function peerLabel(mp) {
  const rank = dataValue(mp, "rank_within_role_peer_group");
  const size = dataValue(mp, "role_peer_group_size");

  if (rank && size) {
    return `${rank}/${size}`;
  }

  return compactLabel(dataValue(mp, "role_peer_group", mp.role), "Standard MP");
}

function trendLabel(mp) {
  const trend = dataValue(mp, "score_change_30d", dataValue(mp, "thirty_day_change"));

  if (trend === undefined || trend === null || trend === "") {
    return "n/a";
  }

  const number = Number(trend);
  if (!Number.isFinite(number)) return String(trend);
  if (number > 0) return `+${formatMetric(number)}`;
  return formatMetric(number);
}

function findEmailInText(value) {
  const match = String(value || "").match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
  return match ? match[0] : "";
}

function getPublicEmail(mp, records) {
  const directFields = [
    mp.email,
    mp.contact_email,
    mp.public_email,
    mp.raw?.email,
    mp.raw?.contact_email,
    mp.raw?.public_email,
    mp.raw?.parliamentary_email
  ];

  for (const field of directFields) {
    const email = findEmailInText(field);
    if (email) return email;
  }

  for (const record of records) {
    const recordFields = [
      record.email,
      record.contact_email,
      record.public_email,
      record.summary,
      record.source_url
    ];

    for (const field of recordFields) {
      const email = findEmailInText(field);
      if (email) return email;
    }
  }

  return "";
}

function boostSubject(mp) {
  return `Common Rank evidence for ${mp.name || "my MP"}`;
}

function boostBody(mp) {
  return [
    `Dear ${mp.name || "MP"},`,
    "",
    "I am writing about your Common Rank / Commons Score profile.",
    "Please publish official, source-linked evidence of constituency work, parliamentary work, delivery, and public value so residents can inspect the public record clearly.",
    "",
    `Constituency: ${mp.constituency || ""}`,
    "",
    "Thank you."
  ].join("\n");
}

function getContactUrl(mp) {
  const memberId = getMemberId(mp);

  if (memberId) {
    return `https://members.parliament.uk/member/${encodeURIComponent(memberId)}/contact`;
  }

  return mp.source_url || "https://members.parliament.uk/members/commons";
}

function buildBoostAction(mp, records) {
  const email = getPublicEmail(mp, records);

  if (email) {
    const subject = encodeURIComponent(boostSubject(mp));
    const body = encodeURIComponent(boostBody(mp));
    return `<a class="boost-action" href="mailto:${escapeHtml(email)}?subject=${subject}&body=${body}">Boost your MP's rank</a>`;
  }

  return `<a class="boost-action" href="${escapeHtml(getContactUrl(mp))}" target="_blank" rel="noopener">Boost your MP's rank</a>`;
}

function warningHtml(mp) {
  const confidence = normalize(confidenceLabel(mp));
  const matchConfidence = normalize(dataValue(mp, "match_confidence", ""));

  if (confidence.includes("low") || ["weak", "uncertain"].includes(matchConfidence)) {
    return `<div class="flag">Low confidence</div>`;
  }

  return "";
}

function buildChipStrip(mp) {
  return `
    <div class="chip-strip" aria-label="Score context">
      <span><b>Confidence</b> ${escapeHtml(confidenceLabel(mp))}</span>
      <span><b>Peer</b> ${escapeHtml(peerLabel(mp))}</span>
      <span><b>Trend</b> ${escapeHtml(trendLabel(mp))}</span>
    </div>
  `;
}

function compactRow(label, value) {
  return `
    <div class="compact-row">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value ?? "n/a")}</strong>
    </div>
  `;
}

function buildScoreBreakdown(mp) {
  const rows = [
    ["Base", dataValue(mp, "base_public_score", calculateMetricScore(mp))],
    ["Confidence", dataValue(mp, "confidence_adjusted_score", calculateOverallScore(mp))],
    ["Role", dataValue(mp, "role_adjusted_score", calculateOverallScore(mp))],
    ["Need", dataValue(mp, "need_alignment_score", 50)],
    ["Final", dataValue(mp, "final_score", calculateOverallScore(mp))]
  ];

  return rows.map(([label, value]) => compactRow(label, `${formatScore(value)} / 100`)).join("");
}

function buildEvidenceConfidence(mp, records) {
  const rows = [
    ["Label", confidenceLabel(mp)],
    ["Multiplier", dataValue(mp, "evidence_confidence_multiplier", "n/a")],
    ["Official", rawValue(mp, "official_source_records_count")],
    ["Parliament", rawValue(mp, "parliament_source_records_count")],
    ["Media share", dataValue(mp, "media_dependency_ratio", "n/a")],
    ["Source records", records.length]
  ];

  return rows.map(([label, value]) => compactRow(label, value)).join("");
}

function buildRoleContext(mp) {
  const rows = [
    ["Role", mp.role || "Standard MP"],
    ["Peer group", dataValue(mp, "role_peer_group", mp.role || "Standard MP")],
    ["Peer rank", peerLabel(mp)],
    ["Percentile", dataValue(mp, "role_peer_percentile", "n/a")]
  ];

  return rows.map(([label, value]) => compactRow(label, value)).join("");
}

function buildNeedAlignment(mp) {
  const rows = [
    ["Label", dataValue(mp, "need_alignment_label", "Neutral")],
    ["Score", `${formatScore(dataValue(mp, "need_alignment_score", 50))} / 100`],
    ["Matches", dataValue(mp, "category_alignment_count", "n/a")],
    ["Ratio", dataValue(mp, "category_alignment_ratio", "n/a")]
  ];

  return rows.map(([label, value]) => compactRow(label, value)).join("");
}

function buildDeliveryChain(mp, records) {
  const rows = [
    ["Promises", rawValue(mp, "promise_records_count") || countRecordsByType(records, ["promise", "pledge", "manifesto"])],
    ["Actions", rawValue(mp, "action_records_count") || countRecordsByType(records, ["action", "question", "debate", "campaign", "meeting", "letter"])],
    ["Follow-up", rawValue(mp, "follow_up_records_count")],
    ["Verified", rawValue(mp, "verified_outcome_records_count")],
    ["Delivery", `${formatScore(getMetricValue(mp, visibleMetrics[2]))} / 100`]
  ];

  return rows.map(([label, value]) => compactRow(label, value)).join("");
}

function buildRawData(mp) {
  const raw = mp.raw || {};
  const rows = [
    ["Member ID", raw.member_id],
    ["Written questions", raw.written_questions_count ?? raw.written_questions_total],
    ["Local questions", raw.local_questions_count ?? raw.written_questions_local],
    ["Votes", raw.votes_count ?? raw.commons_votes_total],
    ["EDMs", raw.edms_count ?? raw.edms_signed],
    ["Focus", raw.focus_items_count],
    ["Interests", raw.registered_interests_count ?? raw.registered_interests_total],
    ["Source records", raw.manual_source_records_count]
  ];

  return rows.map(([label, value]) => compactRow(label, value ?? 0)).join("");
}

function sourceRecordLabel(record) {
  const type = escapeHtml(record.type || record.record_type || "source");
  const sourceType = escapeHtml(record.source_type || record.evidence_type || record.source_connector || "source");
  return `${type} / ${sourceType}`;
}

function buildSourceLinks(records) {
  if (!records.length) {
    return `<div class="source-empty">No matched source records.</div>`;
  }

  return `
    <ul class="source-list">
      ${records.map(record => {
        const summary = escapeHtml(record.summary || "Source record");
        const url = escapeHtml(record.source_url || "");
        const label = sourceRecordLabel(record);
        const title = url
          ? `<a href="${url}" target="_blank" rel="noopener">${summary}</a>`
          : `<span>${summary}</span>`;

        return `
          <li>
            ${title}
            <small>${label}</small>
          </li>
        `;
      }).join("")}
    </ul>
  `;
}

function auditDetail(entry) {
  const bits = [
    entry.source_name || entry.connector,
    `${safeNumber(entry.records_found)} found`,
    entry.scored ? "scored" : "not scored",
    entry.run_mode ? `mode ${entry.run_mode}` : ""
  ].filter(Boolean);

  return bits.map(escapeHtml).join(" / ");
}

function buildAuditSection(title, entries) {
  if (!entries.length) {
    return `
      <div class="audit-section compact">
        <h5>${escapeHtml(title)}</h5>
        <span>None</span>
      </div>
    `;
  }

  const rows = entries.map(entry => {
    const url = entry.endpoint_or_url || "";
    const source = url.startsWith("http")
      ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(entry.source_name || entry.connector)}</a>`
      : `<span>${escapeHtml(entry.source_name || entry.connector)}</span>`;

    const error = entry.error ? `<em>${escapeHtml(entry.error)}</em>` : "";

    return `
      <li>
        ${source}
        <small>${auditDetail(entry)}</small>
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
    return `<div class="source-empty">No source audit entries available.</div>`;
  }

  return auditSections.map(section => {
    const entries = auditEntries.filter(entry => section.statuses.includes(entry.status));
    return buildAuditSection(section.title, entries);
  }).join("");
}

function buildSourcesConsidered(index) {
  return `
    <div class="lazy-sources" data-source-index="${index}">
      <button type="button" class="load-sources" onclick="renderSourcesForCard(${index})">Show sources</button>
    </div>
  `;
}

function accordion(title, content, open = false) {
  return `
    <details class="score-accordion"${open ? " open" : ""}>
      <summary>${escapeHtml(title)}</summary>
      <div class="accordion-body">${content}</div>
    </details>
  `;
}

function buildWhyThisScore(mp, index, records) {
  return `
    <details class="why-panel">
      <summary>Why this score?</summary>
      <div class="why-grid">
        ${accordion("Score breakdown", buildScoreBreakdown(mp), true)}
        ${accordion("Evidence confidence", buildEvidenceConfidence(mp, records))}
        ${accordion("Role context", buildRoleContext(mp))}
        ${accordion("Need alignment", buildNeedAlignment(mp))}
        ${accordion("Delivery chain", buildDeliveryChain(mp, records))}
        ${accordion("Sources considered", buildSourcesConsidered(index))}
        ${accordion("Raw data", buildRawData(mp))}
      </div>
    </details>
  `;
}

function buildMetricRows(mp) {
  return visibleMetrics.map(metric => {
    return scoreRow(metric.label, getMetricValue(mp, metric));
  }).join("");
}

function renderSourcesForCard(index) {
  const mp = displayedMps[index];
  const target = document.querySelector(`[data-source-index="${index}"]`);

  if (!mp || !target || target.dataset.loaded === "true") return;

  const records = getRecordsForMp(mp);
  const auditEntries = getAuditForMp(mp);
  target.dataset.loaded = "true";
  target.innerHTML = `
    <div class="source-evidence">
      <h4>Matched records</h4>
      ${buildSourceLinks(records)}
    </div>
    <div class="source-audit">
      <h4>Sources considered</h4>
      ${buildSourceAudit(auditEntries)}
    </div>
  `;
}

function render(mps) {
  displayedMps = sortedByVisibleScore(mps);

  rankingsEl.innerHTML = displayedMps.map((mp, index) => {
    const rank = index + 1;
    const overallScore = calculateOverallScore(mp);
    const records = getRecordsForMp(mp);

    const photoBlock = mp.photo_url
      ? `<img class="photo" src="${escapeHtml(mp.photo_url)}" alt="">`
      : `<div class="photo placeholder">${escapeHtml(getInitials(mp.name))}</div>`;

    return `
      <article class="card">
        <div class="card-topline">
          <span class="card-rank" aria-label="Rank ${rank}">${rank}</span>
          <span class="kicker">${escapeHtml(mp.party || "Independent")}</span>
        </div>

        <div class="card-main">
          <div class="portrait-wrap">
            ${photoBlock}
          </div>

          <div class="identity">
            <h2>${escapeHtml(mp.name)}</h2>
            <p>${escapeHtml(mp.constituency)}</p>
          </div>

          <div class="hero-score">
            <span>${formatScore(overallScore)} / 100</span>
          </div>
        </div>

        ${warningHtml(mp)}
        ${buildChipStrip(mp)}

        <div class="scores">
          ${buildMetricRows(mp)}
        </div>

        ${buildWhyThisScore(mp, index, records)}

        <div class="actions">
          ${buildBoostAction(mp, records)}
        </div>
      </article>
    `;
  }).join("");
}

function filterMps() {
  const query = searchInput.value.toLowerCase();

  const filtered = allMps.filter(mp => {
    return [
      mp.name,
      mp.constituency,
      mp.party,
      mp.role,
      dataValue(mp, "role_peer_group", ""),
      dataValue(mp, "confidence_label", ""),
      dataValue(mp, "need_alignment_label", "")
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
