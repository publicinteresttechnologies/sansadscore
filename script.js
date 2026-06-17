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

function getInitials(name) {
  return name
    .split(" ")
    .map(part => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function render(mps) {
  rankingsEl.innerHTML = mps.map(mp => {
    const legalFlag = mp.legal_flag
      ? `<div class="flag">${mp.legal_flag}</div>`
      : "";

    const photoBlock = mp.photo_url
      ? `<img class="photo" src="${mp.photo_url}" alt="">`
      : `<div class="photo placeholder">${getInitials(mp.name)}</div>`;

    const variableRows = Object.entries(mp.variables)
      .map(([label, value]) => scoreRow(label, value))
      .join("");

    return `
      <article class="card">
        <div class="card-top">
          <div class="rank">#${mp.rank}</div>

          ${photoBlock}

          <div class="identity">
            <h2>${mp.name}</h2>
            <p>${mp.constituency} | ${mp.party}</p>
          </div>

          <div class="grade">${mp.grade}</div>
        </div>

        ${legalFlag}

        <div class="scores">
          ${variableRows}
        </div>

        <div class="verdict">
          ${mp.verdict}
        </div>

        <div class="actions">
          <a href="${mp.source_url || "#"}" target="_blank" rel="noopener">Sources</a>
          <button onclick="shareCard(${mp.rank})">Share</button>
        </div>
      </article>
    `;
  }).join("");
}

function shareCard(rank) {
  const mp = allMps.find(item => item.rank === rank);

  if (!mp) return;

  const text = `Commons Score: #${mp.rank} ${mp.name} — Grade ${mp.grade}`;

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

async function loadData() {
  const response = await fetch("data/ranked_mps.json", { cache: "no-store" });
  const data = await response.json();

  allMps = data.mps;
  lastUpdatedEl.textContent = `Last updated: ${data.last_updated}`;

  render(allMps);
}

searchInput.addEventListener("input", filterMps);

loadData();
