# FedRAMP 20x KSI Catalog Collector Specification

## Philosophy

This spec defines the runtime collector that pulls the FedRAMP 20x KSI catalog from its canonical upstream at [github.com/FedRAMP/rules](https://github.com/FedRAMP/rules), validates it against pinned safety rules, diffs against the local TAP grid, and submits the resulting changes through the `tap_cares` GRIFT import surface.

It supersedes the **authorship-tooling approach** previously documented in `spec-fedramp-20x-ksi-v0.md` (`req-fedramp-20x-ksi-refresh` + related): a CI-generated wave shipped inside the plugin repo via a nightly GitHub Action and a 974-line `skills/refresh-ksi-catalog/refresh.py` tool. That path is being fully deprecated and removed. The plugin has no current users, so there is no migration concern and no transitional dual path.

The new architecture inverts the locus of catalog collection from **plugin authoring time** to **installation runtime**. A local TAP installation collects, validates, diffs, and merges catalog content directly into its own grid, with every run observable as an on-grid `CollectionJob`. The plugin's role narrows to: ship the models, edges, dimensions, and seed waves needed for a cold-start install; everything after first install is collector-driven.

Long-term — likely after `tap_cares` emitters land — a complementary emitter will close the loop by pushing local-instance updates back to the FedRAMP/rules repo, making a local TAP installation the canonical authoring path for the public catalog. That is explicitly out of scope for v0.

## Vocabulary

This spec inherits the catalog vocabulary (Theme, Indicator, Certification Class, Controls, KSI) from `spec-fedramp-20x-ksi-v0.md` § Vocabulary. Collector-specific terms:

- **Collector** — the on-grid `Collector` node registered by `tap_cares.registry`; the entity that the scheduler / manual invocation targets.
- **Collection Run** — one invocation of the collector, materialized as a `CollectionJob` on the grid.
- **Pinned schema** — the byte-exact copy of the FedRAMP consolidated-rules JSON Schema that the collector validates fetched upstream content against. Lives in the plugin source tree; updating it requires a reviewed PR.
- **Block flag** — a safety violation severe enough to halt the run before any grid mutation.
- **Warn flag** — a safety concern that is logged but does not halt the run.

## Goals

|    |               |                                                                 |
| :---: | ---        | ---                                                             |
| 1. | Runtime         | Catalog collection happens at the local TAP installation, not in plugin CI |
| 2. | Observable      | Every run produces an on-grid `CollectionJob` with status, timestamps, error context, and links to imported GRIFT batches |
| 3. | Safe            | Block-level safety violations abort the run before any grid mutation |
| 4. | Diff-Driven     | The submitted batch contains only the delta between fetched upstream and live grid state |
| 5. | Deterministic   | Entity IDs are stable derivations of catalog codes, so re-runs upsert in place |
| 6. | tap_cares-Native | Built strictly on the `CollectorBase` / `submit_collector_grift` contracts; no special-cased plumbing |

## Requirements

| RID | Name | Status | Notes |
| --- | --- | :---: | --- |
| req-fedramp-20x-ksi-collector-class | [Collector Class](#collector-class) | Proposed | `KSICollector(CollectorBase)` registered at AppConfig.ready() |
| req-fedramp-20x-ksi-collector-fetch | [Upstream Fetch](#upstream-fetch) | Proposed | HTTPS fetch from raw.githubusercontent.com |
| req-fedramp-20x-ksi-collector-pin | [Pinned Schema and UUID Namespace](#pinned-schema-and-uuid-namespace) | Proposed | Schema + UUIDv5 namespace ported from refresh.py's pinned/ into plugin source |
| req-fedramp-20x-ksi-collector-safety | [Runtime Safety Model](#runtime-safety-model) | Proposed | Block / warn flags applicable at runtime; CI-specific checks dropped |
| req-fedramp-20x-ksi-collector-diff | [Live Diff Against Grid](#live-diff-against-grid) | Proposed | Prior state read from local grid; not from replayed waves |
| req-fedramp-20x-ksi-collector-grift | [GRIFT Batch Output](#grift-batch-output) | Proposed | One batch per run via `submit_collector_grift`; `description_json` carries collection-v0 metadata |
| req-fedramp-20x-ksi-collector-mass-deletion | [Mass-Deletion Guard](#mass-deletion-guard) | Proposed | >10% deprecation ratio aborts the run as a block flag |
| req-fedramp-20x-ksi-collector-job-result | [CollectionJob Result Shape](#collectionjob-result-shape) | Proposed | What gets recorded on success and failure |
| req-fedramp-20x-ksi-collector-test-strategy | [Test Strategy](#test-strategy) | Proposed | Fixture-based unit tests + optional live-fetch integration test |
| req-fedramp-20x-ksi-collector-deprecation | [Deprecation of Authorship Tooling](#deprecation-of-authorship-tooling) | Proposed | Removes refresh.py, GitHub Action, submodule, skill directory |
| req-fedramp-20x-ksi-collector-future | [Future Work](#future-work) | Proposed | Emitter loop, delete semantics, scheduler integration |

---

### Collector Class
----
RID: `req-fedramp-20x-ksi-collector-class`
Status: `Proposed`

The runtime collector is a `CollectorBase` subclass, `KSICollector`, that lives in the plugin code and is registered into `collector_registry` at app startup.

#### Implementation

- Module: `plugins/fedramp_20x_ksi/collectors/ksi_catalog.py`.
- Class: `class KSICollector(CollectorBase)`.
- `run()` orchestrates the pipeline: fetch → schema-validate → diff vs grid → safety-check → assemble GRIFT → `submit_collector_grift`.
- KSI-specific configuration lives as class attributes (URL, schema path, UUID namespace, deletion threshold). v0 does not introduce per-instance configuration — the framework `CollectorConfig` shape (just the two entity IDs) is sufficient.
- Registration happens in `plugins/fedramp_20x_ksi/apps.py` inside `Fedramp20xKsiConfig.ready()`:

```python
def ready(self) -> None:
    from tap_cares.registry import register_collector
    from plugins.fedramp_20x_ksi.collectors.ksi_catalog import KSICollector

    register_collector("ksi-catalog", KSICollector)
```

- The registered key is `ksi-catalog`; with `__module__`-based scope inference, the full registry key persisted on the on-grid `Collector` node is `plugins.fedramp_20x_ksi.collectors.ksi_catalog:ksi-catalog`.
- Seeding the on-grid `Collector` node itself happens via a GRIFT seed file in `plugins/fedramp_20x_ksi/grift/collector.grift.json` so a fresh install picks it up via `import_plugin_grift`.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-class-1 | CollectorBase Subclass | Proposed | `KSICollector` inherits from `tap_cares.collectors.CollectorBase` and implements `run()`. | |
| req-fedramp-20x-ksi-collector-class-2 | AppConfig Registration | Proposed | `Fedramp20xKsiConfig.ready()` registers the class via `register_collector("ksi-catalog", KSICollector)`. | |
| req-fedramp-20x-ksi-collector-class-3 | On-Grid Seed | Proposed | A GRIFT seed file creates the on-grid `Collector` node with `collector_registry = "plugins.fedramp_20x_ksi.collectors.ksi_catalog:ksi-catalog"`. | |
| req-fedramp-20x-ksi-collector-class-4 | No Per-Instance Config in v0 | Proposed | KSI-specific configuration is class-level constants; the v0 `CollectorConfig` contract is unchanged. | |

---

### Upstream Fetch
----
RID: `req-fedramp-20x-ksi-collector-fetch`
Status: `Proposed`

The collector fetches the consolidated rules document directly over HTTPS from the FedRAMP/rules repo. No git, no submodule, no auth.

#### Implementation

- Pinned URL: `https://raw.githubusercontent.com/FedRAMP/rules/main/fedramp-consolidated-rules.json`.
- Library: `urllib.request` from stdlib (no new dependency). Future revision may move to `httpx` if retry/backoff sophistication is needed.
- Hard cap on response body size: 10 MiB. Anything larger aborts the run as a block flag (`UPSTREAM_OVERSIZED`).
- Strict `Content-Type` check: must be `application/json` or `text/plain`; anything else aborts as a block flag (`UPSTREAM_BAD_CONTENT_TYPE`).
- Connection + read timeout: 30 s each. Network or HTTP failures fail the run via the standard exception path; the `CollectionJob.error_summary` carries the underlying error type and message.
- The fetched body is treated strictly as data. No code path interprets fetched strings as URLs to follow, paths to read, or instructions of any kind. (Carries forward `req-fedramp-20x-ksi-refresh-11`.)

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-fetch-1 | HTTPS GET Only | Proposed | The collector fetches via HTTPS GET; no git, no clone, no shell. | |
| req-fedramp-20x-ksi-collector-fetch-2 | Pinned URL | Proposed | The fetch URL is a class constant. Changes require code review. | |
| req-fedramp-20x-ksi-collector-fetch-3 | Body Size Cap | Proposed | Bodies > 10 MiB abort the run with block flag `UPSTREAM_OVERSIZED`. | |
| req-fedramp-20x-ksi-collector-fetch-4 | Content-Type Check | Proposed | Non-JSON `Content-Type` aborts the run with block flag `UPSTREAM_BAD_CONTENT_TYPE`. | |
| req-fedramp-20x-ksi-collector-fetch-5 | Failure Surface | Proposed | Network errors fail the `CollectionJob` and surface in `error_summary`. | |
| req-fedramp-20x-ksi-collector-fetch-6 | Content As Data | Proposed | Fetched content is never used as URL, path, or instruction. | |

---

### Pinned Schema and UUID Namespace
----
RID: `req-fedramp-20x-ksi-collector-pin`
Status: `Proposed`

Two pinned files survive from the old refresh tooling, but they relocate from the tool's `pinned/` directory into the plugin's normal source tree:

- `plugins/fedramp_20x_ksi/collectors/pinned/source_schema.json` — byte-exact JSON Schema for the upstream consolidated-rules document. The collector validates fetched content against this; schema drift is a block flag.
- `plugins/fedramp_20x_ksi/collectors/pinned/uuid_namespace.txt` — UUIDv5 namespace string. Theme entity_ids derive from `uuid5(namespace, f"ksi_theme:{code}")`; indicator entity_ids derive from `uuid5(namespace, f"ksi_indicator:{code}")`. This must never change.

Updating either file is a deliberate, reviewed code change. The collector does not auto-update them, ever.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-pin-1 | Pinned Schema Location | Proposed | Pinned schema lives at `plugins/fedramp_20x_ksi/collectors/pinned/source_schema.json`. | Carried over byte-exact from the old skill's pinned/. |
| req-fedramp-20x-ksi-collector-pin-2 | Pinned Namespace Location | Proposed | UUIDv5 namespace lives at `plugins/fedramp_20x_ksi/collectors/pinned/uuid_namespace.txt`. | Same value as today's `0197fed0-4000-7000-8000-000000000100`. |
| req-fedramp-20x-ksi-collector-pin-3 | Entity ID Derivation | Proposed | Theme and indicator entity IDs derive from `uuid5(namespace, "<kind>:<code>")`, identical to today's tool. | |
| req-fedramp-20x-ksi-collector-pin-4 | No Auto-Update | Proposed | The collector never writes to either pinned file. | |

---

### Runtime Safety Model
----
RID: `req-fedramp-20x-ksi-collector-safety`
Status: `Proposed`

The safety check set is a deliberate subset of the existing `req-fedramp-20x-ksi-safety` model. CI-specific checks (commit metadata, submodule integrity, signing) are dropped because they don't apply to a runtime HTTPS fetch; the deterministic content-shape checks survive.

#### Retained checks (block-class)

| Code | Trigger |
| --- | --- |
| `SCHEMA_DRIFT` | Fetched JSON fails validation against the pinned schema. |
| `UNKNOWN_FIELD` | Fetched content contains a key not declared in the pinned schema's `properties`. |
| `STRUCTURAL_CAP` | Catalog exceeds size caps: total bytes > 10 MiB, > 20 themes, > 100 indicators per theme, > 100 KiB per string field, > 200 items per array. |
| `CHARACTER_CLASS` | Any string field contains a Unicode BiDi override character or a control character other than `\t` / `\n`. |
| `MASS_DELETION` | Diff would deprecate > 10% of live indicators in one run (see `req-fedramp-20x-ksi-collector-mass-deletion`). |
| `UPSTREAM_OVERSIZED` | Fetch body > 10 MiB (see `req-fedramp-20x-ksi-collector-fetch`). |
| `UPSTREAM_BAD_CONTENT_TYPE` | Non-JSON content-type (see `req-fedramp-20x-ksi-collector-fetch`). |

#### Retained checks (warn-class)

| Code | Trigger |
| --- | --- |
| `DENYLIST_PHRASE` | A string field matches the safety denylist (prompt-injection heuristics). |
| `OUTLIER_STRING_LENGTH` | A string field is dramatically longer than the field's historical norm. |

Warn-class flags do **not** halt the run. They are recorded in the run's GRIFT batch `description_json.safety` array. Today's `CollectionJob` model doesn't carry warning detail; the lightweight surface is the `description_json`. Richer in-run status/log emission is tracked in `tap_cares` backlog (`req-tap-cares-collector-job-logs`).

#### Dropped checks

| Code | Why dropped |
| --- | --- |
| `INTEGRITY_REWIND` | No submodule pointer to compare against; we fetch live state, not a pointer advance. |
| `ORIGIN_MISMATCH` (git URL) | We're fetching from a pinned HTTPS URL; the host/path *is* the origin check. |
| `commit_author_drift` (warn) | No commit log in a live JSON fetch. |
| `low_quality_commit_message` (warn) | Same. |
| `signed` / `verified` warnings | Same. |

The safety denylist content moves from `skills/refresh-ksi-catalog/safety/denylist.json` to `plugins/fedramp_20x_ksi/collectors/safety/denylist.json` byte-for-byte.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-safety-1 | Block Flags Halt | Proposed | Any retained block-class flag aborts the run before `submit_collector_grift` is called. | |
| req-fedramp-20x-ksi-collector-safety-2 | Job Marked FAILED | Proposed | A block flag sets `CollectionJob.status = FAILED` and writes a summary to `error_summary`. | |
| req-fedramp-20x-ksi-collector-safety-3 | Warn Flags Recorded | Proposed | Warn-class flags appear in the submitted GRIFT batch's `description_json.safety` array. | |
| req-fedramp-20x-ksi-collector-safety-4 | Denylist Ported | Proposed | The existing safety denylist content is moved into the plugin's `collectors/safety/` directory. | |
| req-fedramp-20x-ksi-collector-safety-5 | Dropped Checks Documented | Proposed | CI-specific checks (integrity rewind, origin URL, commit metadata) are not implemented and are documented as not-applicable. | |

---

### Live Diff Against Grid
----
RID: `req-fedramp-20x-ksi-collector-diff`
Status: `Proposed`

Prior state for the diff is the **live local TAP grid**, not a replay of shipped wave files. The collector reads existing `ksi_theme` and `ksi_indicator` entities via an approved read surface (search system or service-layer reads) and compares them to the fetched upstream by `code`.

This drops the wave-replay machinery entirely. Empty grid (fresh install) → every fetched theme/indicator classifies as `new`. Grid already at upstream-current → diff is empty → no GRIFT batch is submitted; the run still succeeds.

#### Implementation

- Read path: a search or read-service call returns the current set of `ksi_theme` + `ksi_indicator` entities, with each entity's `code` field plus enough state to detect modifications (statement text, classes, status, etc.).
- Comparison: by `code` for both themes and indicators, since codes are the stable upsert keys (`req-fedramp-20x-ksi-models`).
- Classification per entity: `new` / `modified` / `unchanged` / `removed`.
- `removed` entities are emitted as a modification setting `status = "deprecated"` (deprecation-via-modification, preserved from `req-fedramp-20x-ksi-reference-4`). They are **not** deleted. Delete semantics are explicitly deferred (see [Future Work](#future-work)).
- `unchanged` entities produce no node entries in the output batch.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-diff-1 | Read From Grid | Proposed | Prior state is read from the local TAP grid via an approved read surface, not from wave files. | |
| req-fedramp-20x-ksi-collector-diff-2 | Compare By Code | Proposed | Themes and indicators are matched by their `code` field. | |
| req-fedramp-20x-ksi-collector-diff-3 | Classify Each Entity | Proposed | Each entity is classified as `new` / `modified` / `unchanged` / `removed`. | |
| req-fedramp-20x-ksi-collector-diff-4 | Deprecation Via Modification | Proposed | `removed` entities are emitted as `status = "deprecated"` modifications, not deletions. | |
| req-fedramp-20x-ksi-collector-diff-5 | Empty Diff Is OK | Proposed | An empty diff produces no GRIFT submission and a SUCCESSFUL job. | |

---

### GRIFT Batch Output
----
RID: `req-fedramp-20x-ksi-collector-grift`
Status: `Proposed`

Each non-empty run produces exactly one GRIFT batch, submitted via `tap_cares.grift.submit_collector_grift`. The batch's `description_json` uses a new runtime format, **`tap.fedramp_20x_ksi.collection-v0`**, which simplifies the old `wave-v0` schema by dropping fields that don't apply at runtime.

#### `collection-v0` shape

`description_json.format == "tap.fedramp_20x_ksi.collection-v0"`

`description_json.data`:

```json
{
  "schema_version": "v0",
  "source": {
    "url": "https://raw.githubusercontent.com/FedRAMP/rules/main/fedramp-consolidated-rules.json",
    "fetched_at": "<RFC3339>",
    "content_sha256": "<hex>",
    "byte_size": <int>,
    "rules_version": "<string>"
  },
  "changes": {
    "themes_new": <int>,
    "themes_modified": <int>,
    "themes_deprecated": <int>,
    "indicators_new": <int>,
    "indicators_modified": <int>,
    "indicators_deprecated": <int>,
    "catalog_size_before": <int>,
    "catalog_size_after": <int>,
    "deletion_ratio": <float>
  },
  "safety": {
    "review_required": <bool>,
    "flags": [
      {"severity": "warn", "code": "DENYLIST_PHRASE", "detail": "..."}
    ]
  }
}
```

Dropped fields vs `wave-v0`:

- `commits[]` — no commit log in a live fetch.
- `wave.index` / `wave.filename` / `wave.is_initial` — collection runs aren't a numbered wave sequence.
- `wave.authored_at` / `wave.authored_by` — `CollectionJob.started_at` and the run's caller carry this.

The batch entity_id is a fresh UUIDv7 per run. Individual theme/indicator entity_ids are the same deterministic UUIDv5 values as today (`req-fedramp-20x-ksi-collector-pin-3`), so GRIFT upsert lands changes on the existing entities rather than creating duplicates.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-grift-1 | One Batch Per Run | Proposed | Non-empty runs submit exactly one GRIFT batch via `submit_collector_grift`. | |
| req-fedramp-20x-ksi-collector-grift-2 | collection-v0 Format | Proposed | The batch's `description_json.format` is `tap.fedramp_20x_ksi.collection-v0`. | |
| req-fedramp-20x-ksi-collector-grift-3 | Source Provenance | Proposed | `description_json.data.source` records URL, fetched_at, content_sha256, byte_size, and the upstream `rules_version` field. | |
| req-fedramp-20x-ksi-collector-grift-4 | Change Counts | Proposed | `description_json.data.changes` reports new/modified/deprecated counts for themes and indicators, plus catalog size before/after and deletion ratio. | |
| req-fedramp-20x-ksi-collector-grift-5 | Safety Recap | Proposed | `description_json.data.safety` records any warn-class flags raised during the run. | Block-class flags abort before this point and produce no batch. |
| req-fedramp-20x-ksi-collector-grift-6 | Deterministic Entity IDs | Proposed | Theme and indicator entity_ids are stable UUIDv5 derivations; re-runs upsert in place. | |
| req-fedramp-20x-ksi-collector-grift-7 | Pinned Schema For description_json | Proposed | A JSON Schema for `collection-v0.data` ships at `plugins/fedramp_20x_ksi/collectors/pinned/collection-v0.schema.json` and the collector validates its own output against it before submission. | |

---

### Mass-Deletion Guard
----
RID: `req-fedramp-20x-ksi-collector-mass-deletion`
Status: `Proposed`

Inherits the spirit of `req-fedramp-20x-ksi-refresh-6`: a single run may not deprecate more than 10% of live indicators. Crossing the threshold raises block flag `MASS_DELETION`, fails the job, and prevents grid mutation.

The ratio is computed against the live grid count: `deprecated_count / live_indicator_count`. With an empty grid, the threshold is undefined and is treated as not triggered (a fresh install can land the whole catalog as `new` without firing).

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-mass-deletion-1 | 10% Threshold | Proposed | Deprecation ratio > 10% of live indicators raises block flag `MASS_DELETION`. | |
| req-fedramp-20x-ksi-collector-mass-deletion-2 | Computed Against Live | Proposed | The denominator is the live indicator count, not the fetched upstream count. | |
| req-fedramp-20x-ksi-collector-mass-deletion-3 | Fresh Install Exempt | Proposed | An empty grid (zero live indicators) does not trigger the guard. | |
| req-fedramp-20x-ksi-collector-mass-deletion-4 | Threshold Adjustable in Code | Proposed | The threshold is a single class constant on `KSICollector`. | Reviewed change, not runtime-configurable. |

---

### CollectionJob Result Shape
----
RID: `req-fedramp-20x-ksi-collector-job-result`
Status: `Proposed`

Reuses the existing `tap_cares` `CollectionJob` lifecycle without extending it. The KSI collector does not need a new status state, new edge type, or new metadata field beyond what `req-tap-cares-collector-job-model` and `req-tap-cares-collector-grift-import` already provide.

#### Successful run (no changes)

- `status = SUCCESSFUL`, `error_summary = ""`, `grift_batches = {"imported": [], "skipped": []}`.

#### Successful run (changes submitted)

- `status = SUCCESSFUL`, `error_summary = ""`, `grift_batches.imported` contains the single batch entity_id this run produced.

#### Failed run

- `status = FAILED`, `error_summary` carries a short, safe summary of the highest-severity block flag (or the underlying exception class + message for non-safety failures).
- `grift_batches = {"imported": [], "skipped": []}` (nothing was submitted).
- Richer per-flag detail is currently out of scope; it lands when `req-tap-cares-collector-job-logs` is implemented.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-job-result-1 | No New Status States | Proposed | The KSI collector uses only the existing `READY`/`RUNNING`/`FAILED`/`SUCCESSFUL` states. | |
| req-fedramp-20x-ksi-collector-job-result-2 | Successful Empty | Proposed | A run that detects no changes still succeeds; `grift_batches.imported` is empty. | |
| req-fedramp-20x-ksi-collector-job-result-3 | Block → FAILED | Proposed | Any retained block flag yields `FAILED` with a corresponding `error_summary`. | |
| req-fedramp-20x-ksi-collector-job-result-4 | Standard Observability | Proposed | The job is queryable through standard `tap_cares` surfaces; no KSI-specific reporting plumbing. | |

---

### Test Strategy
----
RID: `req-fedramp-20x-ksi-collector-test-strategy`
Status: `Proposed`

Two test surfaces:

1. **Unit tests** (fast, no network). Inject upstream content via dependency injection: the collector class exposes its `fetch_upstream()` method as overridable, and tests subclass `KSICollector` (or monkey-patch the class method) to return canned fixtures. Fixtures live at `plugins/fedramp_20x_ksi/tests/fixtures/ksi_catalog/`:
   - `current.json` — a known-good copy of the upstream content (committed to the repo, refreshed manually as needed).
   - `mass_deletion.json` — variant that triggers `MASS_DELETION`.
   - `schema_drift.json` — variant that fails pinned-schema validation.
   - `unknown_field.json` — variant with an extra top-level key.
   - `oversized.json` — variant that breaches a structural cap.
   - `denylist_warn.json` — variant containing a denylist phrase.

2. **Live-fetch integration test** (slow, requires network). Gated by a pytest marker (`@pytest.mark.live_fetch`) so it can be opted out of in CI by default. Verifies the real HTTPS fetch round-trips and parses, but does not assert on the resulting diff (since upstream content changes).

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-test-strategy-1 | Fixture-Injected Unit Tests | Proposed | Unit tests cover happy path, all block flags, and warn flags by overriding `fetch_upstream()` with fixtures. | |
| req-fedramp-20x-ksi-collector-test-strategy-2 | Pinned Fixture Committed | Proposed | `current.json` ships in the repo so tests are deterministic. | |
| req-fedramp-20x-ksi-collector-test-strategy-3 | Live Fetch Test Gated | Proposed | A `@pytest.mark.live_fetch` integration test verifies real network fetch and parsing; skipped by default. | |
| req-fedramp-20x-ksi-collector-test-strategy-4 | End-to-End Via tap_cares | Proposed | A unit test invokes `enqueue_collection(collector)` and asserts that the `CollectionJob` transitions through the expected states and produces the expected `grift_batches`. | |

---

### Deprecation of Authorship Tooling
----
RID: `req-fedramp-20x-ksi-collector-deprecation`
Status: `Proposed`

The catalog refresh authorship tooling is fully removed in this phase. Concretely:

#### Code and infrastructure deletions

- `plugins/fedramp_20x_ksi/skills/refresh-ksi-catalog/` (entire directory, including `refresh.py`, `SKILL.md`, `pinned/`, `safety/`, `state/`, and the `upstream/` submodule).
- The submodule entry for `upstream/` in the plugin's `.gitmodules`.
- `.github/workflows/refresh-catalog.yml` (the nightly action in the plugin's own repo).
- Any `skills` entry referencing `refresh-ksi-catalog` in `plugins/fedramp_20x_ksi/tap-plugin.toml`.

#### Surviving content moves

- `pinned/source_schema.json` → `plugins/fedramp_20x_ksi/collectors/pinned/source_schema.json` (byte-exact).
- `pinned/uuid_namespace.txt` → `plugins/fedramp_20x_ksi/collectors/pinned/uuid_namespace.txt` (byte-exact).
- `safety/denylist.json` → `plugins/fedramp_20x_ksi/collectors/safety/denylist.json` (byte-exact).
- Useful algorithmic functions from `refresh.py` (parsing, validation against pinned schema, UUID derivation, structural caps, character-class gates, deletion-ratio computation, denylist scan) are ported into `plugins/fedramp_20x_ksi/collectors/ksi_catalog.py` as private module functions. The functions are *re-implemented* against the new shape (no submodule context, no commit metadata) rather than copied wholesale; the goal is a clean module ~200–400 LOC rather than a 974-line port.

#### Existing v0 spec impact

The following requirements in `spec-fedramp-20x-ksi-v0.md` change status as part of this phase:

| RID | New Status | Notes |
| --- | --- | --- |
| `req-fedramp-20x-ksi-refresh` | `Deprecated` | Authorship-tooling architecture; superseded by this spec. Notes the supersession explicitly. |
| `req-fedramp-20x-ksi-wave-schema` | `Deprecated` | `wave-v0` format is replaced by `collection-v0` (see `req-fedramp-20x-ksi-collector-grift`). Existing waves in the repo will be scrubbed (`req-fedramp-20x-ksi-collector-deprecation-3`) so no historical `wave-v0` payload survives in shipped data. |
| `req-fedramp-20x-ksi-safety` | `Deprecated` | Replaced by `req-fedramp-20x-ksi-collector-safety`. The retained checks survive; CI-specific ones drop. |
| `req-fedramp-20x-ksi-reference` | `Revised` | Catalog still ships some seed data via GRIFT (the on-grid `Collector` node itself + dimension), but the "catalog content distributes as a sequence of dated waves" contract is dropped. New body language captures the post-collector shape. |

Models (`ksi_theme`, `ksi_indicator`), edges (`CONTAINS_INDICATOR`), icons, dimensions, status, classes, controls, NIST crosswalk plans — all unaffected.

#### Database state on existing dev installs

Per direction from spec review: the existing data in any developer's local TAP grid can be wiped and re-collected from a fresh KSI collector run. No migration of historical wave provenance. The collector's first run on an empty grid will land the complete current catalog as `new`.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-deprecation-1 | Code Removed | Proposed | `skills/refresh-ksi-catalog/`, the submodule, the nightly GitHub Action, and any manifest references are deleted in this phase. | |
| req-fedramp-20x-ksi-collector-deprecation-2 | Content Migrated | Proposed | Pinned schema, UUID namespace, and denylist move byte-exact into `plugins/fedramp_20x_ksi/collectors/`. | |
| req-fedramp-20x-ksi-collector-deprecation-3 | Old Waves Scrubbed | Proposed | The existing `ksi-initial-*.grift.json` and any subsequent `ksi-wave-*.grift.json` files are deleted; the manifest's `[grift]` section drops references to them. The on-grid `Collector` seed and `dimension.grift.json` survive. | |
| req-fedramp-20x-ksi-collector-deprecation-4 | v0 Spec Status Sync | Proposed | `req-fedramp-20x-ksi-refresh`, `-wave-schema`, `-safety`, and `-reference` are updated in `spec-fedramp-20x-ksi-v0.md` per the table above, with cross-references to this spec. | |

---

### Future Work
----
RID: `req-fedramp-20x-ksi-collector-future`
Status: `Proposed`

Items intentionally deferred:

1. **Scheduled refresh.** Once `tap_cares` ships a scheduler (`req-tap-cares-v0-scheduler`), the KSI collector becomes the first concrete consumer. v0 KSI collector runs are triggered manually (Django shell, management command, or admin button).
2. **Emitter loop back to FedRAMP/rules.** When `tap_cares` emitters land, a complementary `KSIEmitter` could push local-instance edits back to the FedRAMP/rules repo as PRs, making a TAP installation the canonical authoring path. The collector's `description_json.data.source` already records the inverse direction; symmetry with an emitter is intentional.
3. **Delete semantics in GRIFT.** Current `tap_grid` GRIFT importer has no explicit delete operation; deprecation-via-modification fills the gap. A proper delete (with entity_id list + reasons) would simplify `req-fedramp-20x-ksi-collector-diff-4` and let the catalog actually shrink rather than accumulate `deprecated` entries forever. Tracked in `tap_grid` spec backlog; the KSI collector adopts it if/when it ships.
4. **Per-flag detail in CollectionJob.** Block flags currently get a single-line `error_summary`. When `req-tap-cares-collector-job-logs` (currently `Backlog`) lands, each flag should attach a structured entry with code, severity, path, and message.
5. **Live-fetch CI gate.** A nightly CI job that runs the `@pytest.mark.live_fetch` test against real upstream would catch upstream-shape changes early. Not a v0 must.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-future-1 | Named Successors | Proposed | The above five future items are named and cross-referenced to their owning specs / backlog items. | |

---

## Status Vocabulary

Same as `spec-fedramp-20x-ksi-v0.md`. Statuses used in this spec at draft time: `Proposed`.

## Cross-References

- `tap_cares/specs/spec-tap-cares-v0.md` — runtime collector / GRIFT-import architecture this spec builds on.
- `tap_cares/specs/spec-tap-cares-collector.md` — `CollectorBase`, `collector_registry`, `submit_collector_grift`, `CollectionJob` contracts.
- `plugins/fedramp_20x_ksi/specs/spec-fedramp-20x-ksi-v0.md` — catalog modeling spec; this collector spec deprecates its refresh-related sections (see `req-fedramp-20x-ksi-collector-deprecation`).
