# Commons Score Methodology

Commons Score is an automated public-record dashboard. It is designed to make the evidence trail easier to inspect, not to deliver a legal, moral, or factual verdict on any MP.

Scores should always be read with the source records, source audit, and limitations below.

## Visible Public Metrics

The public dashboard uses four visible metrics.

| Metric | Weight | What it is intended to indicate |
|---|---:|---|
| Constituency Work | 30% | Visible public activity connected to a constituency or local issues. |
| Parliamentary Work | 30% | Visible participation in parliamentary processes such as questions, votes, EDMs, speeches, committees, or bills where available. |
| Delivery Track | 25% | Evidence that a promise, campaign, action, follow-up, or outcome chain exists in public records. |
| Public Value | 15% | Public-value signals such as cost, funding, IPSA-related context, or other public-benefit evidence where available. |

Older generated data may still contain compatibility names such as `Constituency Focus` and `Promise Follow-Through`. The public interface maps these to the current visible labels until the next data refresh replaces them.

## Final Score Calculation

Commons Score calculates the public score in stages.

1. `base_public_score`: the four visible public metrics using the weights above.
2. `confidence_adjusted_score`: the base score multiplied by an evidence-confidence multiplier from 0.85 to 1.00. Confidence can reduce uncertainty, but it never boosts above the base score.
3. `role_adjusted_score`: 80% confidence-adjusted score and 20% role peer percentile, so MPs are compared partly against broadly similar Commons roles.
4. `final_score`: 85% role-adjusted score and 15% need-alignment score.

The public `score` field equals `final_score`.

## What Each Metric Currently Uses

### Constituency Work

Current signals include:

- local written questions where the constituency or constituency tokens appear in the question text
- Parliament Members API focus item counts
- source records classified as action, question, debate, campaign, meeting, letter, speech, follow-up, or verified outcome when they are visibly local
- when available in newer data, need-alignment diagnostics that compare visible MP activity with major local issue categories

### Parliamentary Work

Current signals include:

- written questions
- Commons vote counts from public member endpoints or Commons Votes discovery where available
- EDM counts
- focus item counts
- parliamentary source records from oral questions, committees, bills, contribution summaries, and Hansard-like signals where available
- modest role adjustment so Speakers, ministers, whips, shadow ministers, and committee chairs are not automatically penalised for having different public activity patterns from ordinary backbench MPs

### Delivery Track

Current signals include:

- promise or pledge records, which receive low credit by themselves
- public action records, which receive more credit
- repeated follow-up records, which receive more credit
- verified official outcomes, which receive the highest credit

Delivery Track is internally weighted as:

| Delivery signal | Internal weight |
|---|---:|
| Promise or pledge | 10% |
| Public action | 25% |
| Repeated follow-up | 25% |
| Verified linked official outcome | 40% |

A verified linked official outcome requires stronger public evidence: an official or parliamentary outcome source, a strong match to the MP/constituency/date context where available, and visible MP action evidence or an explicit linked-action flag. Media alone is not treated as verified delivery. MP websites are treated as weak self-claim evidence unless confirmed by stronger sources.

### Public Value

Current signals include:

- source records about costs, public value, IPSA, expenses, funding, or public-benefit outcomes
- public records that can reasonably indicate value to constituents or taxpayers

IPSA-related signals are context. They are not automatic praise, blame, or evidence of wrongdoing.

## Source Hierarchy

Commons Score weights sources by evidential strength.

1. Official Parliament sources and official public bodies are stronger evidence.
2. Registered interests are transparency evidence, not evidence of wrongdoing.
3. MP websites and contact pages are weak self-claim evidence unless confirmed elsewhere.
4. Media and GDELT are discovery sources only. They can point to possible promises, campaigns, or outcomes, but they do not prove delivery by themselves.

The project avoids accusations of corruption, claims about private intent, and legal conclusions. It scores visible public evidence, not character.

## Source Records and Audit

`data/source_records.json` can contain two complementary layers:

- `records`: matched public source records used as evidence or diagnostics
- `source_audit`: sources considered for each MP, including used sources, diagnostic-only sources, context-only sources, discovery-only sources, no-match results, skipped fast-mode connectors, failed checks, and TODO connectors

Skipped, failed, and TODO sources should remain visible so readers can see what was considered and what still needs improvement.

## Known Limitations and TODOs

- IPSA numeric parsing is not yet wired. Current IPSA handling is page/source discovery and diagnostic context, not a reliable spend calculation.
- Direct Hansard speech counts are not yet reliable. The updater currently uses contribution summary or Hansard-like signals where accessible without keys.
- ONS/local constituency context is not yet scored as a direct condition measure.
- Media findings should not be treated as verified outcomes.
- Some public APIs are best-effort and may change shape, fail, rate-limit, or return sparse results.
- Generated scores depend on available public data and may understate work that is not visible in the connected sources.

## Interpreting Scores

A higher score means the current public-record pipeline found more visible, source-linked activity under the current methodology. A lower score may mean less visible activity, missing connector coverage, sparse public data, or a role/activity pattern not fully captured by the current sources.

Commons Score is therefore best used as an inspection tool: start with the score, then inspect the records, audit trail, and methodology before drawing conclusions.
