# KSI Finding Profile Specification

## Philosophy

The Finding Profile is a dedicated detail page for a single Finding — the full story of *why this finding exists*, presented in one place. It surfaces the finding's identity (name, status, description), the system(s) it applies to, the KSI indicator(s) it relates to, and the supporting evidence collected against it.

The page is the natural drill-down from the genericom open-alerts table: clicking a finding's title navigates here. It is also an entry point from any future surface that lists or counts findings (alert badges, search results, dashboards).

In v0 the page is read-only. Lifecycle controls (resolving, attaching evidence, editing classification) are out of scope; that workflow will land alongside the Resolution model and the broader compliance-workflow iteration. Exception coverage is also out of scope for v0 — the seeded `COVERS_FINDING` edge exists in the graph but is not yet rendered on this page; it will be added once exception display is standardized across the plugin.

The page mirrors the visual structure of the KSI Indicator Profile (`spec-fedramp-20x-ksi-indicator-profile.md`) intentionally: hero header, sectioned body, breadcrumb, the same typography, chip styles, and table conventions. The two profiles together establish the consistent look-and-feel that subsequent profile pages (Asset, Evidence, Exception, Resolution) will inherit.

The page receives the finding's `entity_id` as a URL query parameter and uses a single gryphon hub-and-spoke query to load the finding plus its full neighborhood — every node connected by a `HAS_FINDING`, `RELATED_INDICATOR`, or `HAS_EVIDENCE` edge — in one pass.

### Why A Plugin-Owned Panel (And Not The Standard Table Panel) For v0

The standard `tap_web` Table Panel (`spec-web-panels-standard-table.md`) is the long-term home for tabular data in TAP, and both tables on this profile *should* eventually fold into it. Three current limits prevent that today:

1. **`column_mode` is `common_metadata`-only.** The KSI table (Code · Name · Relationship · Description) and Evidence table (Verdict · Name · Kind · Note + expand) need plugin-defined column sets that the standard panel cannot yet express.
2. **No row-detail / click-to-expand.** The Evidence table's expand-on-click reveal of the full description / scanner output has no analog in the standard panel.
3. **No inline-payload mode.** The standard panel always re-executes a linked Search. Both finding-profile tables are filtered slices of the *same* subgraph the parent panel already loaded for its hero/identity rendering; routing them through `USES_SEARCH` would mean three searches per page render (one for the profile, one per table) parameterized on `entity_id`, and we'd still hit the column-customization wall.

**Decision.** v0 ships as a single plugin-owned panel that loads the neighborhood once and embeds two Tabulator instances driven by that in-page JSON payload. The genericom open-alerts panel (`spec-genericom-open-alerts-table.md`) sets the precedent: same shape, same justification, same Tabulator footprint.

**Refactor signal.** Fold both tables into the standard Table Panel when *all three* of the following land:

- `column_overrides` (or equivalent custom-column mechanism) on the standard panel.
- A row-detail / expand-on-click feature on the standard panel.
- An inline-payload binding mode that lets a panel render off pre-loaded data instead of always re-executing a Search.

Until then, "two Tabulator instances inside a plugin-owned panel" is the right level of investment.

## Goals

|    |              |                                                                 |
| :---: | ---       | ---                                                             |
| 1. | Polished           | Visually refined profile layout consistent with the indicator profile |
| 2. | One-Page Story     | All directly-connected context for the finding — system(s), KSIs, evidence — visible without navigating |
| 3. | Multi-System Aware | The system field can render a comma-separated list when a finding spans multiple assets |
| 4. | KSI-In-Context     | Related KSIs displayed inline with their short descriptions, not just code references |
| 5. | Evidence Drill-In  | Evidence is row-per-evidence with click-to-expand for the full description / scanner output |
| 6. | Plugin-Owned       | Panel type and page live in the KSI plugin |
| 7. | Single-Query Load  | All neighborhood data loaded in one gryphon hub-and-spoke pass |
| 8. | Tabulator-Backed   | KSI and Evidence tables use Tabulator for consistency with other tap_web tables, with a clear refactor path back into the standard Table Panel |

## Requirements

| RID | Name | Status | Notes |
| --- | --- | :---: | --- |
| req-ksi-finding-profile-panel | [Finding Profile Panel Type](#finding-profile-panel-type) | Proposed | Plugin-registered panel type for single-finding display |
| req-ksi-finding-profile-data | [Data Loading](#data-loading) | Proposed | Gryphon hub-and-spoke query loads finding + system/KSI/evidence neighborhood |
| req-ksi-finding-profile-header | [Hero Header](#hero-header) | Proposed | Name, status badge, breadcrumb |
| req-ksi-finding-profile-meta | [Identity Section](#identity-section) | Proposed | System(s), description, status |
| req-ksi-finding-profile-ksi-table | [Related KSIs Table](#related-ksis-table) | Proposed | Table of related indicators with short descriptions |
| req-ksi-finding-profile-evidence-table | [Evidence Table](#evidence-table) | Proposed | Row-per-evidence table with click-to-expand details |
| req-ksi-finding-profile-page | [Page and Navigation](#page-and-navigation) | Proposed | Page seeded via GRIFT; reachable from open-alerts table |
| req-ksi-finding-profile-open-alerts-link | [Open Alerts Title Linkage](#open-alerts-title-linkage) | Proposed | Genericom open-alerts table title cell links to the finding profile |

---

### Finding Profile Panel Type
----
RID: `req-ksi-finding-profile-panel`
Status: `Proposed`

The finding profile is a dedicated panel type registered by the KSI plugin.

#### Implementation
- Panel type lives in `plugins/fedramp_20x_ksi/panels/finding_profile/__init__.py`.
- Registered in `panel_type_registry` during `Fedramp20xKsiConfig.ready()`.
- Panel type slug: `fedramp-20x-ksi-finding-profile`.
- Panel reads `entity_id` from `request.GET` query parameters.
- Required assets:
  - `static/fedramp_20x_ksi/css/panel-ksi-finding-profile.css` — layout styling that re-uses the visual vocabulary of the indicator profile (hero gradient, section titles, chips, breadcrumb).
  - `static/fedramp_20x_ksi/js/panel-ksi-finding-profile.js` — initializes the KSI and Evidence Tabulator instances from embedded JSON payloads.
  - Tabulator CSS + JS are pulled from the existing `tap_web/css/lib/tabulator.min.css` and `tap_web/js/lib/tabulator.min.js` assets — no new vendor copy.
- No editor view in v0.
- See the Philosophy section "Why A Plugin-Owned Panel (And Not The Standard Table Panel) For v0" for the standard-table-panel tradeoff and refactor signals.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-finding-profile-panel-1 | Plugin-Owned Panel Type | Proposed | The panel type class lives in the KSI plugin package. | |
| req-ksi-finding-profile-panel-2 | Registered At Startup | Proposed | The panel type is registered in `panel_type_registry` during `AppConfig.ready()`. | |
| req-ksi-finding-profile-panel-3 | Reads Entity ID From Query Params | Proposed | The panel reads `entity_id` from `request.GET` to identify the finding. | |

---

### Data Loading
----
RID: `req-ksi-finding-profile-data`
Status: `Proposed`

The profile panel loads the finding and its full one-hop neighborhood via a single gryphon hub-and-spoke query.

#### Implementation
- `get_view_context()` reads `entity_id` from `request.GET`.
- Executes the standard hub-and-spoke gryphon: `MATCH (hub)-[e]-(neighbor) WHERE hub.entity_id = $entity_id RETURN hub, e, neighbor`.
- The neighborhood will include:
  - **Inbound `HAS_FINDING`** edges from one or more system/asset nodes (any entity type).
  - **Outbound `RELATED_INDICATOR`** edges to KSI indicator nodes, with a `relationship_type` edge property.
  - **Outbound `HAS_EVIDENCE`** edges to evidence nodes, with `support_kind` and optional `note` edge properties.
- The panel walks the returned subgraph in Python and builds a structured view-model:
  - `finding` — flat dict of finding fields.
  - `systems` — ordered list of `{entity_id, entity_type, name}` for every `HAS_FINDING` source. Multi-system findings render as a comma-separated list in the identity section.
  - `ksis` — ordered list of `{entity_id, code, name, description, relationship_type}` for every `RELATED_INDICATOR` target.
  - `evidence` — ordered list of `{entity_id, name, kind, description, support_kind, note}` for every `HAS_EVIDENCE` target.
- Default subgraph layer is `extended` so any `icon_url` or computed presentation fields surface naturally.
- If the finding is missing or the entity_id is invalid, the panel renders an error state rather than crashing.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-finding-profile-data-1 | Single Gryphon Query | Proposed | Finding, systems, KSIs, and evidence are loaded in one hub-and-spoke gryphon query. | |
| req-ksi-finding-profile-data-2 | Multi-System Support | Proposed | The view-model represents `HAS_FINDING` parents as a list, not a single value. | |
| req-ksi-finding-profile-data-3 | Edge Properties Captured | Proposed | `RELATED_INDICATOR.relationship_type`, `HAS_EVIDENCE.support_kind`, and `HAS_EVIDENCE.note` are surfaced into the view-model. | |
| req-ksi-finding-profile-data-4 | Graceful Missing Entity | Proposed | Missing or invalid `entity_id` renders an error state rather than crashing. | |

---

### Hero Header
----
RID: `req-ksi-finding-profile-header`
Status: `Proposed`

The top of the profile shows the finding's identity at a glance.

#### Implementation
- **Breadcrumb** — `FedRAMP 20x KSI / Findings / <finding name>` styled identically to the indicator profile's breadcrumb. The "Findings" segment is non-navigational in v0 (no findings index page yet); it stays as plain text.
- **Hero block** with the same gradient background as the indicator profile.
- **Name** — primary `<h1>` (the finding's `name`).
- **Status badge** — pill showing `open` / `resolved`. Style derived from the indicator profile status badge but with finding-specific colors:
  - `open` — warning / amber
  - `resolved` — success / green
- The hero contains no class badges (findings don't carry classes); the right side of the hero is left for the status badge alone.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-finding-profile-header-1 | Name Prominent | Proposed | The finding's name is the primary visual element of the hero. | |
| req-ksi-finding-profile-header-2 | Status Badge | Proposed | Status is displayed as a styled badge with distinct colors per value. | |
| req-ksi-finding-profile-header-3 | Breadcrumb | Proposed | A breadcrumb leads back to `/fedramp-ksi`; "Findings" is a static segment in v0. | |

---

### Identity Section
----
RID: `req-ksi-finding-profile-meta`
Status: `Proposed`

A definition-list-style block of the finding's core facts: System(s) and Description.

#### Implementation
- Rendered immediately below the hero, before the KSI table.
- Two stacked rows of label + value:
  - **System(s)** — comma-separated list of system names. Each name links to its entity (`/grid/<entity_id>` or whatever the standard entity-viewer URL is in this build). Order: stable by `entity_id` so refreshes don't reshuffle.
  - **Description** — the finding's `description` rendered as plain text (no markdown). Long descriptions wrap; no truncation in this section.
- Empty descriptions render the section's row as `—` rather than collapsing — the slot is meaningful even when blank.
- Status is *not* repeated here; it lives in the hero badge.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-finding-profile-meta-1 | Multi-System Comma List | Proposed | When a finding has multiple `HAS_FINDING` parents, the System(s) row shows a comma-separated list of names. | |
| req-ksi-finding-profile-meta-2 | System Name Links | Proposed | Each system name links to the system's entity view. | |
| req-ksi-finding-profile-meta-3 | Description Rendered | Proposed | The finding's `description` is rendered as plain text in the identity section. | |

---

### Related KSIs Table
----
RID: `req-ksi-finding-profile-ksi-table`
Status: `Proposed`

A compact table of every KSI indicator related to this finding, with their short descriptions inline so reviewers don't have to context-switch to look them up.

#### Implementation
- Section header: "Related Indicators".
- Rendered as a Tabulator table, initialized from a JSON payload embedded in the panel's HTML (no separate Search call). Same library and embedded-payload pattern as the genericom open-alerts panel.
- Layout: `fitColumns`. No pagination (KSI counts per finding are small — typical 1, structurally bounded by how many KSIs a finding can plausibly relate to).
- Columns:
  - **Code** — KSI code in monospace, formatted as a link to the indicator profile (`/fedramp-ksi/indicator?entity_id=<uuid>`). Custom Tabulator formatter producing an `<a>` element.
  - **Name** — indicator name, plain text.
  - **Relationship** — `relationship_type` from the `RELATED_INDICATOR` edge property, rendered via a Tabulator formatter as a colored pill (`violation`, `passing`, `informational`, `other`). Color vocabulary aligned with the genericom open-alerts table's relationship pills.
  - **Description** — the indicator's `description` field, full-text wrap (`formatter: "textarea"`), no truncation in v0.
- The table renders even when there is exactly one related indicator (do not collapse the table to a single card).
- If the finding has zero related indicators (data anomaly), Tabulator's `placeholder` shows: "No related indicators."

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-finding-profile-ksi-table-1 | Always A Table | Proposed | Related KSIs render as a Tabulator table even when there is only one row. | |
| req-ksi-finding-profile-ksi-table-2 | Code Links To Profile | Proposed | The KSI code cell is a link to that indicator's profile page. | |
| req-ksi-finding-profile-ksi-table-3 | Relationship Pill | Proposed | The relationship_type renders as a colored pill consistent with the genericom open-alerts vocabulary. | |
| req-ksi-finding-profile-ksi-table-4 | Description Inline | Proposed | The indicator's short description is shown inline in the same row. | |
| req-ksi-finding-profile-ksi-table-5 | Empty State | Proposed | If there are zero related indicators, the Tabulator `placeholder` displays an empty-state message. | Should not occur in seeded data |
| req-ksi-finding-profile-ksi-table-6 | Tabulator-Backed | Proposed | The table is initialized via Tabulator using the existing `tap_web/js/lib/tabulator.min.js` asset; no new vendor copy. | |

---

### Evidence Table
----
RID: `req-ksi-finding-profile-evidence-table`
Status: `Proposed`

A row-per-evidence table summarizing every `HAS_EVIDENCE` artifact attached to the finding, with a click-to-expand pattern that reveals the full evidence description/output.

#### Implementation
- Section header: "Evidence".
- Rendered as a Tabulator table, initialized from a JSON payload embedded in the panel's HTML (same library and embedded-payload pattern as the KSI table and the genericom open-alerts panel).
- Layout: `fitColumns`. No pagination; per-finding evidence counts are small.
- Columns (collapsed-row state):
  - **Verdict** — `support_kind` from the `HAS_EVIDENCE` edge (`passing` / `violation` / `informational`), rendered via a Tabulator formatter as a colored pill.
  - **Name** — evidence name, plain text.
  - **Kind** — evidence `kind` (`screenshot` / `scanner_output` / `policy_doc` / `attestation` / `log_excerpt` / `other`), rendered via a Tabulator formatter as a small monospace tag.
  - **Note** — the optional `note` from the `HAS_EVIDENCE` edge, single-line truncated by Tabulator with the full text in a `title` attribute for hover.
- Row expansion: click-to-expand is implemented via Tabulator's `rowFormatter` + a per-row click handler that toggles a detail `<div>` appended below the row's natural cell area. The detail `<div>` contains the evidence's full `description` inside a `<pre>` block with word-wrap so multi-line scanner output (e.g. raw `dig` output with leading whitespace) preserves its layout.
- A chevron control rendered in a synthetic last column rotates 90° on expand to indicate state. Clicking anywhere on the row — not just the chevron — toggles expansion.
- Expansion is per-row independent; multiple rows may be expanded simultaneously.
- No client-side fetching — descriptions are rendered into the embedded JSON payload up front and toggled via DOM class. Sizes are bounded; the seeded DNSSEC `dig` output is the expected upper bound and is small enough.
- If the finding has zero evidence, Tabulator's `placeholder` shows: "No evidence attached."

#### Development
- Tabulator's first-class `rowFormatter` hook is the right surface for the inline detail strip; reaching for native HTML `<details>` would bypass Tabulator's row-management and cause virtual-scroll / sort glitches if those features are added later.
- Click handler must distinguish row-clicks from cell-clicks that should fall through (e.g. clicking the Name link in the future) — for v0 there are no in-row interactive elements, so plain row-click is fine; revisit when columns gain links.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-finding-profile-evidence-table-1 | Row Per Evidence | Proposed | Each evidence artifact renders as one Tabulator row. | |
| req-ksi-finding-profile-evidence-table-2 | Verdict Pill | Proposed | The HAS_EVIDENCE.support_kind renders as a colored pill in its own column via a Tabulator formatter. | |
| req-ksi-finding-profile-evidence-table-3 | Click-To-Expand | Proposed | Clicking the row toggles a detail strip showing the evidence description. | Implemented via Tabulator `rowFormatter` |
| req-ksi-finding-profile-evidence-table-4 | Independent Expand | Proposed | Multiple rows may be expanded at the same time. | |
| req-ksi-finding-profile-evidence-table-5 | Preformatted Description | Proposed | Evidence description renders inside a `<pre>` block with word-wrap so scanner output preserves layout. | |
| req-ksi-finding-profile-evidence-table-6 | Empty State | Proposed | If the finding has no evidence, the Tabulator `placeholder` displays an empty-state message. | |
| req-ksi-finding-profile-evidence-table-7 | Tabulator-Backed | Proposed | The table is initialized via Tabulator using the existing `tap_web/js/lib/tabulator.min.js` asset; no new vendor copy. | |

---

### Page and Navigation
----
RID: `req-ksi-finding-profile-page`
Status: `Proposed`

The profile page is seeded via GRIFT and reachable by URL.

#### Implementation
- Page seeded via a new GRIFT bundle: `grift/finding-profile-page.grift.json`.
- The bundle creates one `page` entity and one `panel` entity, connected by a `USES_PANEL` edge with a `hotlink` property pointing the page's `profile` slot at the finding-profile panel.
- Page slug: `/fedramp-ksi/finding`.
- Page is accessed at its slug URL with the finding's entity_id as a query parameter: `/fedramp-ksi/finding?entity_id=<uuid>`.
- Page layout: single column, single row containing the profile panel (mirrors the indicator profile page's layout).
- The bundle is registered in `tap-plugin.toml` under `[grift]` as `finding_profile_page`.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-finding-profile-page-1 | GRIFT Seeded | Proposed | Page and panel are seeded via plugin GRIFT. | |
| req-ksi-finding-profile-page-2 | Query Param Navigation | Proposed | The page reads the finding identity from a URL query parameter. | |
| req-ksi-finding-profile-page-3 | Single-Column Layout | Proposed | The page has a single column with the profile panel as its sole occupant. | |

---

### Open Alerts Title Linkage
----
RID: `req-ksi-finding-profile-open-alerts-link`
Status: `Proposed`

The genericom open-alerts table — currently the only place findings are listed — is updated so the title cell links to this profile page.

#### Implementation
- Edit `plugins/genericom/static/genericom/js/panel-open-alerts.js`:
  - Add a `titleCellFormatter` that renders the title as an `<a>` with `href="/fedramp-ksi/finding?entity_id=" + row.finding_id`.
  - Wire it onto the Title column.
- Edit `plugins/genericom/panels/open_alerts/__init__.py`:
  - Add `finding_id` to each emitted row dict (already known internally as `finding_id`; just promote it to the row payload).
- The link uses `target="_self"` (default) — clicking navigates in-place. Findings detail is single-page, not a quick-view popover.
- No styling change beyond standard link affordance (blue text, hover underline) consistent with other in-table links in the build.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-finding-profile-open-alerts-link-1 | Title Is A Link | Proposed | The Title column in the genericom open-alerts table renders each title as a link. | |
| req-ksi-finding-profile-open-alerts-link-2 | Correct Target | Proposed | The link points at `/fedramp-ksi/finding?entity_id=<finding_id>`. | |
| req-ksi-finding-profile-open-alerts-link-3 | finding_id In Row Payload | Proposed | The open-alerts `_build_rows` output includes `finding_id` for every row. | |

---

## Future Work

- **Fold KSI + Evidence tables into the standard `tap_web` Table Panel.** Trigger: the standard panel gains *all three* of (a) custom-column / `column_overrides` support, (b) row-detail / click-to-expand, and (c) an inline-payload binding mode that lets the panel render off pre-loaded data instead of always re-executing a Search. At that point this profile's two Tabulator instances should be replaced by two standard Table Panel instances bound to subgraph-derived inline payloads, and the same refactor should sweep up the genericom open-alerts panel.
- **Exception coverage panel** — render an active-exception banner above the description when a `COVERS_FINDING` edge points at this finding from an `active` exception. Held for v1 alongside a standardized exception-display vocabulary.
- **Resolution panel** — once the Resolution model lands, surface the resolution metadata (who, when, how) on resolved findings.
- **Inline edit** — allow status changes, evidence attach/detach, and KSI re-classification directly from the profile.
- **Asset graph mini-viz** — a small Cytoscape sub-graph showing the finding's neighborhood (system → finding → KSI, plus evidence orbiters).
- **History timeline** — once history is wired through plugin models, render the finding's revision history as a timeline section.
- **External correlation IDs** — when the finding model gains a `source_identifier`, surface it with a copy-to-clipboard control.
- **Severity indicator** — once severity lands, render a severity badge in the hero alongside the status badge.
- **Findings index page** — a top-level `/fedramp-ksi/findings` listing; once it exists the breadcrumb's "Findings" segment becomes a navigational link.
- **Print layout** — optimized print stylesheet for audit documentation of individual findings.

## Status Vocabulary

| Status States |  |
| --- | --- |
| Proposed |  |
| Approved for Development | Requirement is accepted and ready to be implemented |
| In Development |  |
| Implemented |  |
| Verified |  |
| Refactoring |  |
| Deprecating |  |
| Deprecated | Not part of the current architecture and should not be implemented |

## RID Format

`req-<application>-<specification>-<feature>-<sub-feature>`

## Requirements Format

`RID: `...``
`Status: `...``

| Sub-Sections | (as needed) |
| --- | --- |
| Status Details |  |
| Implementation |  |
| Development |  |
| Acceptance Criteria |  |
| Future |  |
