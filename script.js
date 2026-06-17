const rankingsEl = document.getElementById("rankings");
const searchInput = document.getElementById("searchInput");
const lastUpdatedEl = document.getElementById("lastUpdated");

let allMps = [];

function scoreRow(label, value) {
  const safeValue = Math.max(0, Math.min(100, Number(value) || 0));

  return `
    <div class="score-row">
      <span>${label}</span>
      <div class="bar">
        <div class="fill" style="width: ${safeValue}%"></div>
      </div>
      <strong>${safeValue}</strong>
    </div>
  `;
}

function render(mps) {
  rankingsEl.innerHTML = mps.map(mp => {
    const legalFlag = mp.legal_flag
      ? `<div class="flag">${mp.legal_flag}</div>`
      : "";

    const photo = mp.photo_url || "https://placehold.co/160x160/222/fff?text=MP";

    return `
      <article class="card">
        <div class="card-top">
          <div class="rank">#${mp.rank}</div>
          <img class="photo" src="${photo}" alt="${mp.name}">
          <div class="identity">
            <h2>${mp.name}</h2>
            <p>${mp.constituency} | ${mp.party} | ${mp.state}</p>
          </div>
          <div class="grade">${mp.grade}</div>
        </div>

        ${legalFlag}

        <div class="scores">
          ${scoreRow("Delivery", mp.delivery)}
          ${scoreRow("Spend Return", mp.spend_return)}
          ${scoreRow("Constituency Relevance", mp.constituency_relevance)}
          ${scoreRow("Parliament Use", mp.parliament_use)}
          ${scoreRow("Evidence Quality", mp.evidence_quality)}
        </div>

        <div class="verdict">
          ${mp.verdict}
        </div>

        <div class="actions">
          <a href="${mp.source_url || "#"}" target="_blank" rel="noopener">Sources</a>
          <button onclick="shareCard('${mp.name}', '${mp.grade}', ${mp.rank})">Share</button>
        </div>
      </article>
    `;
  }).join("");
}

function shareCard(name, grade, rank) {
  const text = `MP Ranking Live: #${rank} ${name} — Grade ${grade}`;

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
      mp.state,
      mp.grade
    ].join(" ").toLowerCase().includes(query);
  });

  render(filtered);
}

async function loadData() {
  const response = await fetch("data/ranked_mps.json");
  const data = await response.json();

  allMps = data.mps;
  lastUpdatedEl.textContent = `Last updated: ${data.last_updated}`;

  render(allMps);
}

searchInput.addEventListener("input", filterMps);

loadData();
