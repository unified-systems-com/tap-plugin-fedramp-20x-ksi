# FedRAMP 20x KSI Plugin Specification

## Philosophy

The FedRAMP 20x KSI plugin models the Key Security Indicator (KSI) catalog defined by the FedRAMP 20x program. Its job is to make the current KSI themes and individual indicators available as first-class TAP graph nodes so other plugins, dashboards, and analyses can attach evidence, observations, and compliance posture to specific indicators.

The plugin stays narrow on purpose. It is responsible for catalog representation and lifecycle, not for evidence collection, control mapping to other frameworks, or compliance scoring. Those are deliberately deferred so the v0 catalog can stabilize before downstream consumers depend on richer semantics.

The FedRAMP 20x program is itself evolving on a rolling-release cadence. The plugin treats the published catalog as the source of truth and resists baking specific indicator content into plugin source code. Catalog content enters the plugin as versioned GRIFT waves shipped alongside the code, authored by a refresh workflow that runs against the live FedRAMP source. Each wave is a point-in-time batch capturing catalog additions, modifications, and deprecations; applied in order they reconstruct the current catalog.

The plugin's TAP-managed types use the `compliance: fedramp-20x` default dimension. Framework identity is carried by the dimension rather than by a singleton root model, leaving room for other compliance frameworks (NIST 800-53, ISO 27001, etc.) to coexist later in parallel plugins under the same `compliance` dimension key.

## Vocabulary

The FedRAMP 20x program renamed its catalog field names on 2025-11-18. The plugin uses the current vocabulary throughout:

- **Theme** — a top-level grouping of related security outcomes, identified by a code like `KSI-IAM`. FedRAMP defines 11 themes as of April 2026. (Previously called "indicator" in the pre-2025-11-18 catalog.)
- **Indicator** — a single measurable security outcome within a theme, identified by a code like `KSI-IAM-01`. Each indicator has pass/fail validation criteria and applies to one or more FedRAMP impact baselines. (Previously called "requirement" in the pre-2025-11-18 catalog.)
- **Baseline** — a FedRAMP impact tier to which an indicator applies. v0 recognizes `low` and `moderate`. Approximately 56 indicators apply at the Low baseline; approximately 61 at the Moderate baseline. Many indicators apply to both.
- **KSI** — the generic term for the Key Security Indicator program. Used when referring to the program as a whole rather than a specific theme or indicator.

Phases (Phase One, Phase Two) are a program-level concept. The plugin tracks whichever phase is currently authoritative and does not model phase as a field on the catalog itself.

## Goals

|    |              |                                                                 |
| :---: | ---       | ---                                                             |
| 1. | Narrow         | v0 models only KSI themes and indicators; no evidence, scoring, or framework crosswalk |
| 2. | Wave-Distributed | Catalog content ships as versioned GRIFT waves authored by the refresh workflow |
| 3. | Dimensioned    | Every TAP-managed type uses the `compliance: fedramp-20x` default dimension |
| 4. | Lifecycle-Aware | Indicators carry an explicit status (draft/published/deprecated) so catalog churn is visible |
| 5. | Refactor-Friendly | Model and edge shape supports a future `compliance_core` plugin without breaking changes |

## Requirements

| RID | Name | Status | Notes |
| --- | --- | :---: | --- |
| req-fedramp-20x-ksi-scope | [Plugin Scope](#plugin-scope) | Implemented | Defines what the plugin covers and excludes |
| req-fedramp-20x-ksi-dimensions | [Dimension Strategy](#dimension-strategy) | Implemented | `compliance: fedramp-20x` default dimensions for every model and edge |
| req-fedramp-20x-ksi-models | [Model Catalog](#model-catalog) | Implemented | `ksi_theme` and `ksi_indicator` |
| req-fedramp-20x-ksi-status | [Indicator Status](#indicator-status) | Implemented | Indicators carry `status` of `draft`, `published`, or `deprecated` |
| req-fedramp-20x-ksi-baselines | [Indicator Baselines](#indicator-baselines) | Implemented | Indicators carry a `baselines` list identifying applicable FedRAMP impact tiers |
| req-fedramp-20x-ksi-validation-json | [Indicator Validation Field](#indicator-validation-field) | Implemented | Indicators carry structured validation criteria as `validation_json` |
| req-fedramp-20x-ksi-edges | [Edge Types](#edge-types) | Implemented | Single `CONTAINS_INDICATOR` edge from theme to indicator |
| req-fedramp-20x-ksi-icons | [Icons](#icons) | Implemented | Generic type-level icons bound to models; 11 per-theme SVGs shipped as static assets |
| req-fedramp-20x-ksi-reference | [Reference Data As GRIFT Waves](#reference-data-as-grift-waves) | Proposed | Catalog ships as versioned GRIFT waves; v0 scaffold ships none yet |
| req-fedramp-20x-ksi-refresh | [Catalog Refresh Workflow](#catalog-refresh-workflow) | Proposed | Authorship-tooling skill scaffold in place; full design deferred |
| req-fedramp-20x-ksi-plugin-validation | [Plugin Validation](#plugin-validation) | Implemented | Structure-level validation passes; loads/runs awaiting INSTALLED_APPS integration |
| req-fedramp-20x-ksi-nongoals | [v0 Non-Goals](#v0-non-goals) | Proposed | Explicitly deferred concerns |

### Plugin Scope
----
RID: `req-fedramp-20x-ksi-scope`
Status: `Implemented`

The plugin models the FedRAMP 20x KSI catalog: themes (e.g. KSI-CNA, KSI-IAM, KSI-MLA) and the individual indicators within each theme.

#### Implementation

The plugin covers:

- KSI themes as first-class TAP nodes
- individual KSI indicators as first-class TAP nodes
- the structural relationship from a theme to its indicators
- structured validation criteria attached to each indicator
- explicit indicator lifecycle status (`draft`, `published`, `deprecated`)
- per-indicator applicable FedRAMP baselines (`low`, `moderate`)

The plugin excludes in v0:

- a `framework` model representing FedRAMP 20x as a node — framework identity is carried by the `compliance: fedramp-20x` dimension instead
- evidence collection, evidence requirements as separate modeled nodes, or evidence-to-indicator graph relationships
- compliance scoring, posture, or assessment outcomes
- crosswalks to other frameworks (NIST 800-53, ISO 27001, SOC 2, etc.)
- assessment-organization-specific data such as 3PAO findings, ATO packages, or POA&Ms
- per-CSP compliance state
- FedRAMP program phase as a modeled field (phase is tracked at the program level, not on individual catalog entries)

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-scope-1 | Catalog Only | Implemented | v0 covers themes and indicators as catalog data, not evidence or scoring. | |
| req-fedramp-20x-ksi-scope-2 | No Framework Node | Implemented | The plugin does not define a `framework` model in v0; framework identity lives in the dimension. | |
| req-fedramp-20x-ksi-scope-3 | No Crosswalks | Implemented | v0 does not model relationships to other compliance frameworks. | |
| req-fedramp-20x-ksi-scope-4 | Phase Not Modeled | Implemented | FedRAMP program phase is not a field on catalog entries; the plugin tracks whichever phase is currently authoritative. | |

### Dimension Strategy
----
RID: `req-fedramp-20x-ksi-dimensions`
Status: `Implemented`

Every TAP-managed type in the plugin declares `{"compliance": "fedramp-20x"}` as its default dimensions.

#### Implementation

The `compliance` dimension key is intended as the shared root for all compliance-framework plugins. Future plugins for NIST 800-53, ISO 27001, SOC 2, etc. should use the same `compliance` key with their own framework-specific value, e.g. `{"compliance": "nist-800-53-rev5"}`.

This convention keeps dimension-scoped queries useful: a single filter on `compliance` dimension key returns all compliance-framework data regardless of source framework, while filtering on the value scopes to one framework.

The plugin does not seed a dimension node describing `compliance: fedramp-20x` in v0. If TAP later adopts the dimension-node convention more broadly (see `tap_grid` dimension specs), the refresh workflow may seed one as part of catalog import.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-dimensions-1 | Default Dimensions Required | Implemented | Each model declares `DEFAULT_DIMENSIONS = {"compliance": "fedramp-20x"}`. | |
| req-fedramp-20x-ksi-dimensions-2 | Edge Default Dimensions Required | Implemented | Each edge definition declares `default_dimensions: {"compliance": "fedramp-20x"}`. | |
| req-fedramp-20x-ksi-dimensions-3 | Shared Compliance Key | Implemented | The `compliance` dimension key is intended as the convention for all future compliance-framework plugins. | |

### Model Catalog
----
RID: `req-fedramp-20x-ksi-models`
Status: `Implemented`

The plugin declares two TAP-managed models: `ksi_theme` and `ksi_indicator`.

#### Implementation

| Model | Purpose | Key fields |
| --- | --- | --- |
| `ksi_theme` | A top-level KSI grouping like KSI-CNA or KSI-IAM | `code`, `name`, `description` |
| `ksi_indicator` | An individual indicator within a theme, e.g. KSI-CNA-01 | `code`, `name`, `description`, `validation_json`, `status`, `baselines` |

Field intent:

- **`code`**: the canonical FedRAMP identifier. For themes: the theme code (e.g. `"KSI-CNA"`). For indicators: the full indicator code (e.g. `"KSI-CNA-01"`). Stable across catalog refreshes and used for upsert keys.
- **`name`**: human-readable name as published by FedRAMP. Canonical entity-metadata field per `req-grid-entity-metadata`.
- **`description`**: human-readable plain-text description as published by FedRAMP.
- **`validation_json`**: structured validation criteria as published by FedRAMP, stored verbatim from source. Indicator-only. Detailed in `req-fedramp-20x-ksi-validation-json`.
- **`status`**: indicator lifecycle state. Indicator-only. Detailed in `req-fedramp-20x-ksi-status`.
- **`baselines`**: list of FedRAMP impact baselines to which the indicator applies. Indicator-only. Detailed in `req-fedramp-20x-ksi-baselines`.

The plugin should not invent validation, naming, or grouping conventions that diverge from what FedRAMP publishes. The refresh workflow is responsible for converting source data into these field shapes; the catalog model itself stays close to the source.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-models-1 | Two Model Set | Implemented | v0 declares exactly two TAP-managed models: `ksi_theme` and `ksi_indicator`. | |
| req-fedramp-20x-ksi-models-2 | Stable Codes For Upsert | Implemented | `code` is the stable identifier used by the refresh workflow for upserts on both models. | |
| req-fedramp-20x-ksi-models-3 | Source-Faithful Fields | Implemented | Catalog content fields preserve FedRAMP's published shape rather than re-interpreting it. | |

#### Open Questions

- Whether `code` should be enforced unique within `compliance: fedramp-20x` at the database level, or only enforced by the refresh workflow's upsert logic. v0 starts with workflow-level enforcement and may tighten later.

### Indicator Status
----
RID: `req-fedramp-20x-ksi-status`
Status: `Implemented`

Each `ksi_indicator` carries a `status` field with one of three values: `draft`, `published`, `deprecated`.

#### Implementation

The status vocabulary in v0 is intentionally small:

- **`draft`**: the indicator appears in source but is not yet finalized for current authorization use
- **`published`**: the indicator is current and authoritative
- **`deprecated`**: the indicator was previously published but has since been retired or superseded

The refresh workflow assigns `status` based on the source data. When an indicator disappears from source between waves, the refresh workflow emits a wave entry marking it `deprecated` rather than deleting it, so historical references in other graph data remain meaningful.

Per-status transition history is not tracked separately by the plugin in v0. Once the TAP history system is wired up for plugin models, indicator history will be captured through the standard mechanism.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-status-1 | Three-Value Status | Implemented | `status` is one of `draft`, `published`, `deprecated`. | Enforced via `FIELD_VALIDATION_SCHEMA` enum |
| req-fedramp-20x-ksi-status-2 | Required On Indicator | Implemented | Every `ksi_indicator` has an explicit `status`; there is no implicit default. | Declared in `CREATE_REQUIRED` |
| req-fedramp-20x-ksi-status-3 | Refresh Marks Removed As Deprecated | Proposed | The refresh workflow marks indicators that disappear from source as `deprecated` rather than deleting them. | Contract declared; implementation lives in the refresh skill |

### Indicator Baselines
----
RID: `req-fedramp-20x-ksi-baselines`
Status: `Implemented`

Each `ksi_indicator` carries a `baselines` list identifying the FedRAMP impact baselines to which the indicator applies.

#### Implementation

The v0 baseline vocabulary is:

- `low`
- `moderate`

`baselines` is a list because indicators commonly apply to both baselines. An indicator that applies to both Low and Moderate carries `["low", "moderate"]`. Ordering within the list is not significant.

The field is required and must contain at least one value. An indicator with no applicable baseline would not be distributed by FedRAMP and should not appear in the plugin catalog.

Baselines are stored as a list field rather than modeled as separate `ksi_baseline` nodes because:

- the baseline vocabulary is small, closed, and publisher-controlled
- no per-baseline metadata beyond the identifier has v0 relevance
- graph traversal on baselines is not a v0 use case

A future requirement may promote baselines to nodes if cross-framework baseline alignment or baseline-specific attributes become interesting.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-baselines-1 | Baseline List Field | Implemented | `ksi_indicator` declares a `baselines` list field. | |
| req-fedramp-20x-ksi-baselines-2 | Two-Value Vocabulary | Implemented | v0 baseline values are `low` and `moderate`; unknown values are rejected. | Enforced via `FIELD_VALIDATION_SCHEMA` enum |
| req-fedramp-20x-ksi-baselines-3 | Non-Empty Required | Implemented | Every indicator has at least one baseline. | Enforced via `minItems: 1` |

#### Future

Promote baselines to first-class `ksi_baseline` nodes with `APPLIES_TO` edges if a concrete graph use case emerges. Current direction keeps them as a flat list.

### Indicator Validation Field
----
RID: `req-fedramp-20x-ksi-validation-json`
Status: `Implemented`

Each `ksi_indicator` carries a `validation_json` field holding the structured validation criteria for the indicator.

#### Implementation

The field stores the validation block from the source FedRAMP 20x catalog verbatim as JSON. The plugin does not impose its own schema on the contents in v0 because the source format is still evolving and committing to a derived schema risks drift.

The refresh workflow is responsible for extracting the validation block from source and writing it into this field. Downstream consumers (evidence plugins, dashboards) should treat the field as informational in v0 rather than as a typed contract.

A future requirement may introduce a separate `ksi_evidence_requirement` model with structured fields and a `REQUIRES_EVIDENCE` edge from indicator to requirement. That migration is non-breaking: the `validation_json` field stays as the source-of-truth blob while structured nodes derive from it.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-validation-json-1 | Source-Faithful Storage | Implemented | `validation_json` stores the source validation block verbatim. | |
| req-fedramp-20x-ksi-validation-json-2 | No Imposed Schema | Implemented | v0 does not impose a derived JSON schema on `validation_json` contents. | Field schema is `{"type": ["object", "null"]}` only |
| req-fedramp-20x-ksi-validation-json-3 | Optional Field | Implemented | `validation_json` may be empty or null when source data lacks a validation block. | |

#### Future

Promote validation criteria to a structured `ksi_evidence_requirement` model with `REQUIRES_EVIDENCE` edges once the source format stabilizes and TAP has a concrete consumer for graph-shaped evidence requirements.

### Edge Types
----
RID: `req-fedramp-20x-ksi-edges`
Status: `Implemented`

The plugin declares one edge type: `CONTAINS_INDICATOR`.

#### Implementation

| Edge | Direction | Description |
| --- | --- | --- |
| `CONTAINS_INDICATOR` | `ksi_theme` → `ksi_indicator` | A theme contains an individual indicator |

The plugin does not define edges for cross-indicator relationships, indicator dependencies, or framework-to-theme containment in v0. Cross-indicator dependencies, where they exist in source data, may be captured in `validation_json` as informational content until there is a concrete graph use case.

If a future `framework` model is introduced (in this plugin or in a future `compliance_core` plugin), a `CONTAINS_THEME` edge would naturally accompany it. Adding that later is non-breaking for `CONTAINS_INDICATOR`.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-edges-1 | Single Edge | Implemented | v0 declares exactly one edge type: `CONTAINS_INDICATOR`. | |
| req-fedramp-20x-ksi-edges-2 | Theme To Indicator Direction | Implemented | The edge points from `ksi_theme` to `ksi_indicator`. | |
| req-fedramp-20x-ksi-edges-3 | Dimensioned Edge | Implemented | The edge declares `default_dimensions: {"compliance": "fedramp-20x"}`. | |

### Icons
----
RID: `req-fedramp-20x-ksi-icons`
Status: `Implemented`

The plugin binds one canonical icon to `ksi_theme` and one to `ksi_indicator` for v0, consistent with TAP's v1 type-level icon contract. The full per-theme icon set ships as static assets for use by dashboards and templates that look up icons by theme code, and for future promotion to canonical icons once instance-level icon overrides land in `tap_grid`.

#### Implementation

TAP's v1 icon contract (`spec-grid-icon.md` `req-grid-icon-type`) binds one icon per entity type via the class-level `ENTITY_ICON` attribute. Per-instance icon overrides are tracked as `req-grid-icon-instance` and are currently `Backlog`. Within that constraint, v0 binds:

- `ksi_theme` → `ENTITY_ICON = "ksi-theme"` (one generic theme icon)
- `ksi_indicator` → `ENTITY_ICON = "ksi-indicator"` (one generic indicator icon)

The plugin also ships 11 per-theme SVGs as static assets under the same `static/fedramp_20x_ksi/icons/` directory:

| Icon key | Theme code | Title |
| --- | --- | --- |
| `ksi-abf.svg` | KSI-ABF | Authorization by FedRAMP |
| `ksi-chm.svg` | KSI-CHM | Change Management |
| `ksi-cna.svg` | KSI-CNA | Cloud Native Architecture |
| `ksi-cye.svg` | KSI-CYE | Cybersecurity Education |
| `ksi-iam.svg` | KSI-IAM | Identity and Access Management |
| `ksi-inc.svg` | KSI-INC | Incident Response |
| `ksi-mla.svg` | KSI-MLA | Monitoring, Logging, and Auditing |
| `ksi-poi.svg` | KSI-POI | Policy and Inventory |
| `ksi-rcp.svg` | KSI-RCP | Recovery Planning |
| `ksi-svc.svg` | KSI-SVC | Service Configuration |
| `ksi-scr.svg` | KSI-SCR | Supply Chain Risk |

These 11 files are not bound to any `ENTITY_ICON` in v0. They are available to dashboards and templates that resolve a static URL directly from a theme's `code` field, and are positioned to become canonical per-theme icons without asset-rework once `req-grid-icon-instance` is implemented.

The exact theme set tracks whatever FedRAMP publishes. If FedRAMP 20x changes theme composition, the icon set and this table update accordingly through the refresh workflow and a spec revision; the list above reflects the authoritative catalog as of April 2026.

Icons follow the TAP `currentColor` convention rather than vendor brand colors. FedRAMP does not publish per-theme iconography; the icons in this plugin are TAP-authored representations.

Known v0 visual limitation: graph views using the default `ENTITY_ICON` resolution path (Cytoscape, etc.) show all themes with the same icon and all indicators with the same icon. Per-theme visual differentiation in v0 requires consumers to look up the appropriate SVG directly by theme `code`. This limitation resolves when `req-grid-icon-instance` is implemented.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-icons-1 | One Type Icon Each | Implemented | `ksi_theme` and `ksi_indicator` each declare one canonical `ENTITY_ICON`. | |
| req-fedramp-20x-ksi-icons-2 | Per-Theme Assets Shipped | Implemented | The 11 per-theme SVGs ship as static assets under `static/fedramp_20x_ksi/icons/`. | Available for template/dashboard lookup by theme code |
| req-fedramp-20x-ksi-icons-3 | CurrentColor Convention | Implemented | Icons use `currentColor` for theming, not vendor brand colors. | |
| req-fedramp-20x-ksi-icons-4 | Ready For Instance Overrides | Implemented | Per-theme SVGs are named and positioned so they become canonical per-theme icons without asset rework once `req-grid-icon-instance` is implemented. | |

#### Future

When `req-grid-icon-instance` is implemented, rebind per-theme icons as instance-level overrides so Cytoscape and other default-icon consumers render each theme with its own icon without dashboards resolving by code.

### Reference Data As GRIFT Waves
----
RID: `req-fedramp-20x-ksi-reference`
Status: `Proposed`

Catalog content ships as versioned GRIFT waves in the plugin's `grift/` directory. Each wave is a point-in-time batch capturing additions, modifications, and deprecations relative to the catalog state implied by all earlier waves.

#### Status Details

Contract declared and documented. No waves shipped yet in v0 scaffold; the first wave is the refresh skill's first job.

#### Implementation

Wave file naming convention:

- `grift/ksi-initial-YYYY-MM-DD.grift.json` — the first wave; a full catalog snapshot
- `grift/ksi-wave-YYYY-MM-DD.grift.json` — subsequent waves; additions, modifications, and deprecations

Lexical filename order matches chronological order for this scheme, and waves apply in that order. Applied cumulatively, the waves reconstruct the current catalog.

Idempotency: each wave uses deterministic entity IDs derived from the theme or indicator `code`. The refresh workflow is responsible for producing stable IDs across runs so re-importing a wave produces the same entity graph.

Deprecation semantics: when source data drops an indicator between refresh runs, the next wave emits a modification that sets `status: deprecated` on that indicator rather than deleting it. Later waves can supersede earlier status decisions if source data resurrects an indicator.

v0 scaffold: the plugin ships no GRIFT wave files yet. The manifest omits the `[grift]` section until the first wave is produced by the refresh workflow. Adding waves is additive and does not require breaking changes to plugin structure.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-reference-1 | Wave-Based Distribution | Proposed | Catalog content distributes as GRIFT waves committed to `grift/` in the plugin repo. | First wave pending refresh skill |
| req-fedramp-20x-ksi-reference-2 | Naming Convention | Implemented | Wave filenames follow `ksi-initial-YYYY-MM-DD.grift.json` for the first wave and `ksi-wave-YYYY-MM-DD.grift.json` for subsequent waves. | Convention documented |
| req-fedramp-20x-ksi-reference-3 | Deterministic Entity IDs | Proposed | Wave entries use deterministic entity IDs derived from the stable `code` field. | UUIDv5 scheme pending refresh skill |
| req-fedramp-20x-ksi-reference-4 | Deprecation Via Modification | Proposed | Missing indicators enter a wave as a modification setting `status: deprecated`, never as a delete. | Contract declared; refresh skill enforces |
| req-fedramp-20x-ksi-reference-5 | Additive Evolution | Proposed | Adding new waves does not require structural changes to the plugin; the manifest is updated to reference new wave files. | |

### Catalog Refresh Workflow
----
RID: `req-fedramp-20x-ksi-refresh`
Status: `Proposed`

The plugin ships a Claude Code skill that fetches the current FedRAMP 20x KSI catalog and generates the next GRIFT wave.

#### Status Details

Placeholder `SKILL.md` in place at `skills/refresh-ksi-catalog/`. Full design — source fetching, diff algorithm, wave file schema beyond GRIFT base shape, UUIDv5 namespace, CI integration — deferred to a dedicated follow-up session.

#### Implementation

The skill lives at `skills/refresh-ksi-catalog/SKILL.md` per `spec-plugin-architecture.md` plugin-skills convention. It is a plugin-owned skill, not a host-level skill.

The refresh skill is authorship tooling, not operator runtime tooling. Its intended audience is the plugin maintainer (or a CI agent acting on the maintainer's behalf). Operators running TAP installations import catalog content by pulling the plugin repo and running plugin-standard GRIFT import; they do not need to run the refresh skill themselves.

Skill responsibilities:

- fetch the current FedRAMP 20x KSI catalog from the authoritative source
- reconstruct the catalog state implied by existing waves in the plugin's `grift/` directory
- diff current source against that reconstructed state
- emit a new `grift/ksi-wave-YYYY-MM-DD.grift.json` file capturing additions, modifications, and deprecations
- produce stable deterministic entity IDs across runs
- mark missing indicators `deprecated` per `req-fedramp-20x-ksi-status` and `req-fedramp-20x-ksi-reference`
- emit no wave file when source matches reconstructed state (no-op)

Intended automation pattern: a GitHub Action in the plugin repo runs the refresh skill on a nightly schedule. When the skill produces a wave file, the action opens a pull request against `main`. A human reviewer inspects the wave and merges.

Skill design is deferred to a follow-up session. The v0 plugin scaffold ships the directory and a placeholder `SKILL.md` so the convention is in place and future work can begin without restructuring.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-refresh-1 | Skill Convention | Implemented | The refresh skill lives at `skills/refresh-ksi-catalog/SKILL.md`. | Placeholder in place |
| req-fedramp-20x-ksi-refresh-2 | Authorship Tooling | Implemented | The skill is authorship tooling for the plugin maintainer; operators are not expected to run it. | Contract documented |
| req-fedramp-20x-ksi-refresh-3 | Wave Output | Proposed | The skill emits a dated `ksi-wave-YYYY-MM-DD.grift.json` when source differs from the reconstructed state; no file when they match. | Pending skill design |
| req-fedramp-20x-ksi-refresh-4 | Deprecation Rule | Proposed | The skill emits `deprecated` status modifications for missing indicators rather than deletions. | Pending skill design |
| req-fedramp-20x-ksi-refresh-5 | CI-Friendly | Proposed | The skill is structured so a GitHub Action can run it headlessly and open a PR with the resulting wave. | Pending skill design |
| req-fedramp-20x-ksi-refresh-6 | Skill Design Deferred | Implemented | The skill's source-fetching strategy, diff algorithm, and wave-file schema beyond GRIFT base shape are specified in a follow-up session. | Placeholder `SKILL.md` flags the open design points |

### Plugin Validation
----
RID: `req-fedramp-20x-ksi-plugin-validation`
Status: `Implemented`

The plugin passes TAP's centralized plugin validation system at the structure level in v0 and is expected to pass `loads` and `runs` validation before broader publication.

#### Status Details

Structure-level validation passes in strict mode. Loads and runs validation require the plugin to be registered in TAP's `INSTALLED_APPS` with migrations applied, which is not part of v0 scaffold by design (see `spec-plugin-architecture.md`).

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-plugin-validation-1 | Structure Validation Required | Implemented | The plugin passes `tap_plugins` structure validation in strict mode. | Verified via `python -m tap_plugins.validate_plugin plugins/fedramp_20x_ksi --strict` |
| req-fedramp-20x-ksi-plugin-validation-2 | Deeper Validation Recommended | Proposed | Authors should run `loads` and `runs` validation before publishing the plugin widely. | Pending `INSTALLED_APPS` integration |

### v0 Non-Goals
----
RID: `req-fedramp-20x-ksi-nongoals`
Status: `Proposed`

This specification does not define:

- a `framework` model representing FedRAMP 20x as a node
- a `ksi_evidence_requirement` model or `REQUIRES_EVIDENCE` edge
- crosswalks to other compliance frameworks
- assessment-organization data such as 3PAO findings, ATO packages, or POA&Ms
- per-CSP compliance state, posture, or scoring
- the implementation details of the refresh skill (deferred to its own session)
- per-indicator iconography
- a derived JSON schema for `validation_json` contents
- FedRAMP program phase as a modeled field

These are intentionally outside the v0 catalog-representation pass.

## Future Work

- Define and design the `refresh-ksi-catalog` skill in detail, including source fetching, diff algorithm, and wave file schema.
- Stand up the nightly GitHub Action in the plugin repo that runs the refresh skill and opens PRs for generated waves.
- Promote `validation_json` to a structured `ksi_evidence_requirement` model with `REQUIRES_EVIDENCE` edges once a concrete consumer exists.
- Introduce a `framework` model (likely in a future `compliance_core` plugin) and add a `CONTAINS_THEME` edge from framework to `ksi_theme`.
- Add crosswalk edges from KSI indicators to controls in other frameworks (NIST 800-53, ISO 27001, etc.).
- Wire indicator change history through TAP's history system once it covers plugin models, allowing indicator drift between waves to be queried as graph data in addition to reading wave files directly.
- Promote `baselines` to first-class `ksi_baseline` nodes if cross-framework baseline alignment becomes relevant.
- Rebind per-theme SVGs as canonical instance-level icons once `req-grid-icon-instance` is implemented in `tap_grid`.
