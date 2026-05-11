# Sunray Licensing Decision

**Date taken:** 2026-05-08
**Decided by:** Cyril MORISSE (sole IP owner)
**Distributor:** oursbl.eu
**Context:** Recorded during the SSOT generation session for the Sunray ecosystem (3 repositories: this server repo + `sunray-worker-cloudflare` + `sunray-worker-fastapi`).

## Decision

| Component | License | Conversion |
|-----------|---------|------------|
| `sunray_core` (free tier — `project_addons/sunray_core/`) | **FSL-1.1-Apache-2.0** | Sliding 2-year window → Apache 2.0 (per release) |
| `sunray_advanced_core` (paid tier "Sunray Enterprise" — `project_addons_advanced/sunray_advanced_core/`) | **Elastic License v2 (ELv2)** | None — perpetual source-available |

**Both licenses forbid third parties from offering Sunray as a hosted or managed service** without a commercial agreement. The Sunray Enterprise tier additionally requires a paid commercial subscription : **9€/month for 20 users + 1€/user above** ; "billed user" = ≥2 connections per month.

## Why

- **Hosting protection.** Prevent extractive resale of the Sunray brand as a hosting service without commercial agreement (would undercut the per-user pricing model).
- **Channel model alignment.** Partners must purchase commercial licenses at standard rates and resell the service themselves — no white-label, no margin-sharing on the per-user fee.
- **Core "Fair Source" narrative.** The 2-year sliding conversion to Apache 2.0 gives an honest "open source eventually" story — important for European-sovereignty positioning and for bus-factor reassurance (Cyril MORISSE is the sole maintainer).
- **Advanced perpetual restriction.** The paid tier must stay paid forever ; ELv2 has no conversion clause, so a v1.0 of advanced does not become free Apache 2.0 in 2 years.

## Beta status

At the time of this decision, Sunray is in beta :

- **Billing is currently inactive.** Customers use Sunray Enterprise for free.
- **License runtime enforcement is not implemented.** No mechanism blocks Enterprise features for non-licensed users (roadmap item #3 in [sunray_ssot.md](../../sunray_ssot.md) Roadmap section).
- **Source-available violations are tolerated** during beta. The Enterprise code is visible in the public repository ; this is accepted while billing and enforcement are not yet active. The position will be reassessed when both go live.

The beta-exit date is currently undefined. It is gated by (a) functional billing infrastructure and (b) license runtime enforcement.

## Implementation

The artefact-level updates required to make this decision visible in the codebase are tracked in the dedicated ticket : **[`tickets/license_update_all_addons.md`](../../tickets/license_update_all_addons.md)** at the meta-repo root.

**Execution status (2026-05-08, Phases 0-4 of the ticket complete):**

- ✅ `project_addons/sunray_core/__manifest__.py` — declared `Other OSI approved licence` with inline comment pointing to FSL-1.1-Apache-2.0
- ✅ `project_addons_advanced/sunray_advanced_core/__manifest__.py` — declared `Other proprietary` (effective ELv2)
- ✅ `project_addons_advanced/sunray_dashboard/__manifest__.py` — declared `Other proprietary` (effective **ELv2** — Sunray Enterprise, aligned with `sunray_advanced_core`). Addon discovered during execution.
- ✅ `appserver-sunray18/LICENSE` (root index) + `LICENSES/FSL-1.1-Apache-2.0.txt` + `LICENSES/ELv2.txt` created
- ✅ `sunray-worker-cloudflare/LICENSE` + `package.json` license field updated
- ✅ `sunray-worker-fastapi/LICENSE` + `pyproject.toml` license field updated
- ✅ READMEs license sections refreshed across all 3 repos (legal-binding parts) ; commercial body wording deferred to SSOT-driven regeneration
- ✅ Server `CLAUDE.md` path correction `advanced_addons/` → `project_addons_advanced/`

**Phase 5 — IP-lawyer review (operator decision 2026-05-08): DEFERRED.**

Cyril MORISSE decided to ship the licensing decision without prior formal legal review. Rationale : (a) the licensor lacks the means to engage IP counsel at this stage of beta ; (b) the intention and spirit of the dual-license model (no extractive resale, paid commercial subscription for advanced features, eventual Fair Source conversion) is now expressed in writing and embedded in the codebase, which is more useful than waiting indefinitely ; (c) the formal review will be revisited and refined later when the project's commercial trajectory justifies the legal cost — likely close to beta exit and billing activation.

This means the published licenses (FSL-1.1-Apache-2.0 for the free core tier + Sunray Dashboard, Elastic License v2 for Sunray Enterprise) are committed as-is. Should a clause prove unenforceable or ambiguous under future IP counsel review, the position will be amended with a versioned successor LICENSE — existing prior-version usage continues under its current grant.

**Remaining (Phase 6 — pending before public commit):**

- ⏳ Replace "Open Source / total transparency" wording in commercial pages with "Source Available / Fair Source" (part of the broader SSOT-driven regeneration)
- ⏳ Cleanup of residual LGPL-3 mentions in `specs/cf_worker_specs/sunray_advanced_deployment_summary.md` and `specs/fastapi-worker-implementation-plan/*.md` — these are old design specs reflecting a superseded "Open Core LGPL + Commercial" model
- ⏳ `package-lock.json` regeneration via `npm install` (currently embeds the stale `LGPL-3.0` from the old `package.json` at root entry)
- ⏳ Coordinated commits per repo + submodule pointer bump in meta-repo

## Trigger for execution

The licensing ticket must be executed (a) before any `LICENSE` file is committed publicly, or (b) before the first public release of `sunray_advanced_core` v1.0, whichever comes first.

## Caveat

This decision was taken between Cyril MORISSE and an AI agent during the SSOT generation session. **Legal review by qualified IP counsel is required** before public adoption — specifically to confirm :

- FSL Permitted Purpose clause matches Sunray's commercial model
- ELv2 clauses are enforceable for the self-hosted advanced subscription
- Commercial subscription terms for `sunray_advanced_core` are draftable in a way compatible with the ELv2 license grant

## See also

- [`sunray_ssot.md`](../../sunray_ssot.md) — meta-repo root — sections **Pricing & Offers**, **Channel & White-label / Distribution**, **Foundation principles**, **Roadmap**
- [`tickets/license_update_all_addons.md`](../../tickets/license_update_all_addons.md) — actionable ticket for the codebase updates
