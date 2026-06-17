# Project registry and repository boundaries

This file exists to stop unrelated Codex tasks from being mixed into the wrong repository.

## Current repository

Repository: `publicinteresttechnologies/sansadscore`

Canonical product in this repository: **Commons Score / SansadScore**

Purpose: public-interest accountability dashboard for UK MPs, with evidence collection, scoring, source records, public ranking UI, and scheduled data updates.

This repository should only contain Commons Score / SansadScore work unless a deliberate migration plan says otherwise.

## Do not build these projects inside this repository

The following are separate projects and should not be implemented as folders, features, or half-built experiments inside `publicinteresttechnologies/sansadscore`.

| Project | Correct target repository | Status |
|---|---|---|
| Justice Clock India | `publicinteresttechnologies/justice-clock-india` | create separate repo |
| UK Sponsored Job Radar | `publicinteresttechnologies/uk-sponsored-job-radar` | create separate repo |
| Will It Leak? / Exam Leak Index | `publicinteresttechnologies/will-it-leak` | create separate repo |
| Synthetic Media Control Plane | `publicinteresttechnologies/synthetic-media-control-plane` | later, only if actively funded/built |

## Codex operating rule

Before starting any Codex task, confirm the selected repository.

- If the task is about Commons Score, use this repository.
- If the task is about Justice Clock India, create/use `justice-clock-india`.
- If the task is about UK sponsored job search, create/use `uk-sponsored-job-radar`.
- If the task is about exam leaks, create/use `will-it-leak`.

If Codex is currently running a non-Commons-Score task inside this repository, stop that task and restart it in the correct repository.

## Immediate cleanup plan

1. Keep `publicinteresttechnologies/sansadscore` as the live Commons Score product.
2. Create separate repos for the three active next projects.
3. Move no code out of this repository unless a later extraction decision is made.
4. Do not let Codex scaffold unrelated products inside this repository.
