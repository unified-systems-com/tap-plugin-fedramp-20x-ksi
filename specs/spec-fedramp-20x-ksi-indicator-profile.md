# KSI Indicator Profile Specification

## Philosophy

The KSI Indicator Profile is a dedicated detail page for viewing a single FedRAMP 20x Key Security Indicator. It provides a polished, information-rich view of everything TAP knows about an indicator — its requirement statement, applicable certification classes, referenced NIST controls, source metadata, and parent theme — in a layout designed for compliance professionals who need to understand an indicator thoroughly.

The page is the natural drill-down from the compliance view table: clicking an indicator code navigates here. In v0 it is read-only and informational. Future iterations will add live evidence status, findings, and assessment data as those systems are built.

The page receives the indicator's entity_id as a URL query parameter and uses a gryphon hub-and-spoke query to load the indicator and its graph neighborhood (parent theme via `CONTAINS_INDICATOR` edge) in a single pass.

## Goals

|    |                    |                                                                                       |
| :---: | ---             | ---                                                                                   |
| 1. | Polished           | Visually refined profile layout — not a raw field dump                                |
| 2. | Complete           | All indicator fields displayed in logically grouped sections                           |
| 3. | Contextual         | Parent theme shown with icon, providing navigational context                          |
| 4. | Class-Aware        | Statement section shows class-variant text with per-class toggle                      |
| 5. | Extensible         | Layout accommodates future sections (evidence, findings) without redesign             |
| 6. | Plugin-Owned       | Panel type and page live in the KSI plugin                                            |

## Requirements

| RID | Name | Status | Notes |
| --- | --- | :---: | --- |
| req-ksi-profile-panel | [Indicator Profile Panel Type](#indicator-profile-panel-type) | Proposed | Plugin-registered panel type for single-indicator display |
| req-ksi-profile-data | [Data Loading](#data-loading) | Proposed | Gryphon hub-and-spoke query loads indicator + theme neighborhood |
| req-ksi-profile-header | [Hero Header](#hero-header) | Proposed | Code, name, status badge, theme badge with icon, class badges |
| req-ksi-profile-statement | [Statement Section](#statement-section) | Proposed | Requirement text with per-class toggle for class_variants |
| req-ksi-profile-metadata | [Metadata Section](#metadata-section) | Proposed | Controls, terms, references in a structured grid |
| req-ksi-profile-changelog | [Change Log Section](#change-log-section) | Proposed | Timeline display of updated_log entries |
| req-ksi-profile-page | [Page and Navigation](#page-and-navigation) | Proposed | Page seeded via GRIFT, navigable from compliance view |

---

### Indicator Profile Panel Type
----
RID: `req-ksi-profile-panel`
Status: `Proposed`

The indicator profile is a dedicated panel type registered by the KSI plugin.

#### Implementation
- The panel type lives in `plugins/fedramp_20x_ksi/panels/indicator_profile/`.
- It is registered in `panel_type_registry` during the KSI plugin's `AppConfig.ready()`.
- The panel type slug is `fedramp-20x-ksi-indicator-profile`.
- The panel reads `entity_id` from `request.GET` query parameters (same pattern as the existing viewer and editor panels).
- Required assets:
  - A dedicated `panel-ksi-indicator-profile.css` for profile layout styling
  - No Tabulator or heavy JS libraries needed — the profile is primarily server-rendered HTML
  - Minimal JS for class-variant toggle (can be inline-safe or a small static file)
- No editor view in v0.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-profile-panel-1 | Plugin-Owned Panel Type | Proposed | The panel type class lives in the KSI plugin package. | |
| req-ksi-profile-panel-2 | Registered At Startup | Proposed | The panel type is registered in `panel_type_registry` during `AppConfig.ready()`. | |
| req-ksi-profile-panel-3 | Reads Entity ID From Query Params | Proposed | The panel reads `entity_id` from `request.GET` to identify the indicator. | |

### Data Loading
----
RID: `req-ksi-profile-data`
Status: `Proposed`

The profile panel loads the indicator and its graph neighborhood via a gryphon hub-and-spoke query.

#### Implementation
- The panel's `get_view_context()` reads `entity_id` from `request.GET`.
- It executes a gryphon hub-and-spoke query: `MATCH (hub)-[e]-(neighbor) WHERE hub.entity_id = $entity_id RETURN hub, e, neighbor`.
- The query returns the indicator node, the parent theme node (via `CONTAINS_INDICATOR` edge), and any other future edges.
- The raw subgraph is passed to the template context — the template renders server-side from the structured data (unlike the compliance view which passes JSON to JS).
- The `extended` subgraph layer provides `icon_url` for the parent theme.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-profile-data-1 | Gryphon Hub-and-Spoke | Proposed | Data loaded via gryphon query through the search service layer. | |
| req-ksi-profile-data-2 | Theme Resolved | Proposed | Parent theme is resolved from the `CONTAINS_INDICATOR` edge in the neighborhood. | |
| req-ksi-profile-data-3 | Graceful Missing Entity | Proposed | If `entity_id` is missing or invalid, the panel renders an error state rather than crashing. | |

### Hero Header
----
RID: `req-ksi-profile-header`
Status: `Proposed`

The top of the profile displays the indicator's identity at a glance.

#### Implementation
- **Code** displayed prominently in a monospace font (e.g., `KSI-IAM-MFA`).
- **Name** as the primary heading (e.g., "Adopting Passwordless Methods").
- **Status badge** — styled pill showing Published / Draft / Deprecated (same styling as compliance view).
- **Theme badge** — parent theme name with per-theme icon, linking back to the compliance view (or scrolling to the theme group). Displayed as a navigational breadcrumb element.
- **Class badges** — applicable certification classes displayed as badge row. All purple if no class_variants; clickable with active highlight if class_variants exist (same behavior as compliance view).

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-profile-header-1 | Code And Name Prominent | Proposed | Code and name are the primary visual elements at the top of the profile. | |
| req-ksi-profile-header-2 | Status Badge | Proposed | Status is displayed as a styled badge consistent with the compliance view. | |
| req-ksi-profile-header-3 | Theme Context | Proposed | Parent theme is shown with icon as a navigational breadcrumb. | |
| req-ksi-profile-header-4 | Class Badges | Proposed | Applicable classes shown as badges; clickable for class_variant indicators. | |

### Statement Section
----
RID: `req-ksi-profile-statement`
Status: `Proposed`

The requirement statement is the core content of the profile.

#### Implementation
- For indicators with a direct `description`: display the statement text in a readable block.
- For indicators with `class_variants`: display the statement for the currently active class. Class badges in the header toggle which variant is shown (same per-row toggle pattern as the compliance view, with fade transition).
- The statement section should have comfortable typography: larger font size than table cells, good line-height, adequate padding.
- If the statement contains markdown-style formatting (e.g., `**Optional:**`), render it as styled text rather than raw markdown syntax.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-profile-statement-1 | Statement Displayed | Proposed | The indicator's requirement statement is prominently displayed. | |
| req-ksi-profile-statement-2 | Class-Variant Toggle | Proposed | For class_variant indicators, clicking class badges swaps the statement with a fade. | |
| req-ksi-profile-statement-3 | Readable Typography | Proposed | Statement text uses comfortable reading typography. | |

### Metadata Section
----
RID: `req-ksi-profile-metadata`
Status: `Proposed`

Structured display of the indicator's reference data: NIST controls, terms, and external references.

#### Implementation
- **NIST Controls** — displayed as a list or grid of control IDs (e.g., `ac-2.2`, `ia-12`). Each control rendered as a compact chip/tag. Future: these will link to NIST control nodes once `req-fedramp-20x-ksi-nist-crosswalk` is implemented.
- **Terms** — list of referenced terms from the `terms` field (e.g., "Information Resource", "Machine-Based (Information Resources)"). Displayed as a simple list or tag set.
- **Reference** — if `reference` and/or `reference_url` are populated, display as a labeled link or citation block.
- Empty fields are omitted rather than showing blank sections.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-profile-metadata-1 | Controls Displayed | Proposed | NIST control IDs shown as chips/tags. | |
| req-ksi-profile-metadata-2 | Terms Displayed | Proposed | Referenced terms shown when present. | |
| req-ksi-profile-metadata-3 | Reference Link | Proposed | External reference displayed as a link when present. | |
| req-ksi-profile-metadata-4 | Empty Fields Omitted | Proposed | Sections with no data are hidden, not shown as empty. | |

### Change Log Section
----
RID: `req-ksi-profile-changelog`
Status: `Proposed`

The indicator's `updated_log` displayed as a timeline of changes.

#### Implementation
- Each `updated_log` entry contains `{date, comment}`.
- Displayed as a vertical timeline or simple date-labeled list, most recent first.
- If `updated_log` is empty, the section is omitted.
- The section is visually distinct (e.g., a muted background or bordered card) to separate it from the active requirement data.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-profile-changelog-1 | Timeline Display | Proposed | Change log entries rendered as a date-labeled list or timeline. | |
| req-ksi-profile-changelog-2 | Reverse Chronological | Proposed | Most recent entries appear first. | |
| req-ksi-profile-changelog-3 | Omitted When Empty | Proposed | Section is hidden if `updated_log` is empty. | |

### Page and Navigation
----
RID: `req-ksi-profile-page`
Status: `Proposed`

The profile page is seeded via GRIFT and navigable from the compliance view.

#### Implementation
- The page is seeded via a GRIFT file in the KSI plugin (`grift/ksi-indicator-profile-page.grift.json`).
- The page slug is `/fedramp-ksi/indicator`.
- The page is accessed at its slug URL with the indicator's entity_id as a query parameter: `/fedramp-ksi/indicator?entity_id=<uuid>`.
- The compliance view's Code column links are updated to navigate to this page instead of the generic entity viewer.
- The profile page's hero header includes a breadcrumb link back to the compliance view (`/fedramp-ksi`).
- The page contains a single panel slot occupied by the indicator profile panel instance.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-ksi-profile-page-1 | GRIFT Seeded | Proposed | Page and panel seeded via plugin GRIFT. | |
| req-ksi-profile-page-2 | Query Param Navigation | Proposed | The page reads the indicator identity from a URL query parameter. | |
| req-ksi-profile-page-3 | Compliance View Links | Proposed | Code links in the compliance view table navigate to this profile page. | |
| req-ksi-profile-page-4 | Breadcrumb Back | Proposed | The profile includes a link back to the compliance view. | |

## Future Work

- **Evidence section**: Show per-indicator evidence coverage — linked evidence artifacts, collection status, gaps.
- **Findings section**: Display active findings, remediation status, and assessment history.
- **NIST control links**: Once `req-fedramp-20x-ksi-nist-crosswalk` is implemented, controls become clickable links to NIST control profile pages.
- **Term links**: Link terms to a future glossary or term-node viewer.
- **Edit mode**: Allow authorized users to annotate indicators with organization-specific notes or evidence mappings.
- **Print layout**: Optimized print stylesheet for audit documentation of individual indicators.

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
