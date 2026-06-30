# Parliament API Coverage Audit

Source inventory: UK Parliament Developer Hub, https://developer.parliament.uk/.

The Developer Hub describes itself as a directory of open data APIs for Parliamentary data, made available under the Open Parliament Licence. It lists the currently supported public data APIs.

This document tracks which official Parliament APIs Commons Score currently uses, which APIs are partially wired, and which APIs are missing or out of scope.

## API directory coverage

| Official API | Developer Hub description | Current repo status | Commons Score relevance | Priority |
|---|---|---|---|---|
| Members | Retrieves Members of the Commons or Lords data | Partially wired | Identity, MP profile, roles, contact, constituency link | Critical |
| Interests | Register of Members' Financial Interests data | Partially/weakly wired through Members endpoint; dedicated Interests API not yet wired | Proof, transparency, public value diagnostics | Critical |
| Commons Votes | Commons voting data | Candidate endpoint exists; probing currently skipped in fast mode | Activity, Public Value | Critical |
| Lords Votes | Lords voting data | Not wired | Out of scope for Commons-only version | None for v1 |
| Oral Questions | Tabled oral questions and motions for the House of Commons | Candidate endpoints exist; skipped in fast mode | Activity, Public Value | High |
| Statutory Instruments | Details of statutory instruments laid before Parliament | Not wired | Public Value, scrutiny, specialist activity | Medium |
| Treaties | Details of treaties laid before Parliament | Not wired | Public Value, scrutiny, foreign affairs activity | Medium |
| Erskine May | Erskine May data | Not wired | Methodology/reference context, not MP scoring | Low |
| Parliament Now | Annunciator / live Parliamentary business data | Not wired | Live/current activity context; not stable historic score by itself | Medium |
| Bills | Bills for both Houses | Candidate endpoints exist; skipped in fast mode | Activity, Delivery, Public Value | Critical |
| Written Questions | Written questions, answers and written ministerial statements | Wired and strongest current source | Activity, Local Focus, Public Value | Critical |
| Committees | Committees for both Houses, including membership, inquiries and publications | Candidate endpoints exist; skipped in fast mode | Activity, Public Value, role context | Critical |

## Current implementation reality

Commons Score currently has a working but incomplete official Parliament data layer.

### Wired now

- Members search for current Commons MPs.
- Written Questions API ingestion.
- Members API counters for registered interests, EDMs, focus items and voting when probed.
- Members API collectors for registered interests, experience, contribution summary and contact when full/deeper collection is used.

### Present but not robust yet

- Commons Votes candidate endpoint.
- Oral Questions candidate endpoints.
- Bills candidate endpoints.
- Committees candidate endpoints.

These are currently treated as skipped in fast mode or tentative probes, not as complete production-grade connectors.

### Missing official APIs

- Dedicated Register of Interests API.
- Statutory Instruments API.
- Treaties API.
- Parliament Now API.
- Erskine May API.
- Lords Votes API, intentionally out of Commons v1 scope.

## Endpoint priorities for Commons Score

### Must wire before calling the product complete

1. Members API full member detail endpoint.
2. Members API Location / Constituency endpoints.
3. Interests API, especially interests-by-member and published register metadata.
4. Commons Votes API, using a documented stable query rather than blind probing.
5. Written Questions API, already present but should be kept as a first-class official source.
6. Oral Questions API.
7. Bills API.
8. Committees API.

### Should wire as context, not direct score inflation

1. Statutory Instruments API.
2. Treaties API.
3. Parliament Now API.

### Keep out of Commons v1

1. Lords Votes API.
2. Lords Interests endpoints inside Members API.

## Mapping to five public metrics

| Metric | Official APIs that should feed it |
|---|---|
| Activity | Written Questions, Oral Questions, Commons Votes, Bills, Committees, Members Contribution Summary |
| Local Focus | Members Location / Constituency, Written Questions, Oral Questions, Members Focus |
| Delivery | Bills, Committees, Written Questions follow-up patterns, official outcome sources when available |
| Public Value | Written Questions, Oral Questions, Commons Votes, Bills, Committees, Statutory Instruments, Treaties |
| Proof | Members, Interests, source audit, official-source counts, register metadata |

## Guardrail

Do not add every API directly into the score just because it exists.

Each connector must declare:

- official endpoint used
- whether it is scored, context-only, diagnostic-only, or out of scope
- which of the five public metrics it affects
- how records are counted
- what failure/skipped state appears in Sources & Methods

## Immediate next implementation tickets

1. Add an official API inventory constant in `config.py` covering the Developer Hub directory.
2. Add source-audit entries for every official API, including missing/out-of-scope ones.
3. Replace tentative Commons Votes / Bills / Committees probes with stable official endpoint calls.
4. Add the dedicated Interests API as the proper source for financial interests instead of relying only on Members sub-endpoints.
5. Add constituency lookup from Members Location endpoints for Local Focus.
