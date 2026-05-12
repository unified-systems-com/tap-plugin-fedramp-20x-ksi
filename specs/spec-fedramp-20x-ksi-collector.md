# FedRAMP 20x KSI Catalog Collector Specification

## Philosophy

This spec defines the runtime collector that pulls the FedRAMP 20x KSI catalog from its canonical upstream at [github.com/FedRAMP/rules](https://github.com/FedRAMP/rules), validates it against pinned safety rules, diffs against the local TAP grid, and submits the resulting changes through the `tap_cares` GRIFT import surface.

It supersedes the **authorship-tooling approach** previously documented in `spec-fedramp-20x-ksi-v0.md` (`req-fedramp-20x-ksi-refresh` + related): a CI-generated wave shipped inside the plugin repo via a nightly GitHub Action and a 974-line `skills/refresh-ksi-catalog/refresh.py` tool. That path is being fully deprecated and removed. The plugin has no current users, so there is no migration concern and no transitional dual path.

The new architecture inverts the locus of catalog collection from **plugin authoring time** to **installation runtime**. A local TAP installation collects, validates, diffs, and merges catalog content directly into its own grid, with every run observable as an on-grid `CollectionJob`. The plugin's role narrows to: ship the models, edges, dimensions, and a single current-time seed file needed for a cold-start install; everything after first install is collector-driven.

v0 deliberately uses HTTPS-only fetch from the upstream raw content URL — not a git clone. This is a short-term simplification, not a long-term posture; it costs us cryptographic provenance (commit signatures, ancestor-of-last-known-SHA verification, author/email visibility) in exchange for fast delivery. A future `GitCollectorBase` abstraction (see [Future Work](#future-work)) will get the provenance chain back and is expected to land soon. Until then the v0 collector compensates with paranoid content-level safety checks — every flag is block-class, no warn tier. The full trust-model caveat is in [Runtime Safety Model](#runtime-safety-model).

Long-term — likely after `tap_cares` emitters land — a complementary emitter will close the loop by pushing local-instance updates back to the FedRAMP/rules repo, making a local TAP installation the canonical authoring path for the public catalog. That is explicitly out of scope for v0.

## Vocabulary

This spec inherits the catalog vocabulary (Theme, Indicator, Certification Class, Controls, KSI) from `spec-fedramp-20x-ksi-v0.md` § Vocabulary. Collector-specific terms:

- **Collector** — the on-grid `Collector` node registered by `tap_cares.registry`; the entity that the scheduler / manual invocation targets.
- **Collection Run** — one invocation of the collector, materialized as a `CollectionJob` on the grid.
- **Pinned schema** — the byte-exact copy of the FedRAMP consolidated-rules JSON Schema that the collector validates fetched upstream content against. Lives in the plugin source tree; updating it requires a reviewed PR.
- **Block flag** — a safety violation; in v0 every safety flag is block-class. Halts the run before any grid mutation.

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
| req-fedramp-20x-ksi-collector-safety | [Runtime Safety Model](#runtime-safety-model) | Proposed | All flags block; CI-specific provenance checks dropped (recovered by future git collector base) |
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

The safety check set is a deliberate subset of the existing `req-fedramp-20x-ksi-safety` model, adapted to runtime context. **Every check is block-class.** The previous warn / block distinction is collapsed: anything the safety model flags fails the run, period. The grid is live; we accept the cost of strictness over the risk of a missed signal slipping through as a "warning."

#### Trust model caveat

HTTPS-only fetch (`req-fedramp-20x-ksi-collector-fetch`) deliberately does **not** carry git-level provenance. We have:

- TLS to GitHub's raw content host
- A pinned URL (host + path)

We do **not** have:

- A cryptographic chain of trust through commit signatures
- Ancestor-of-last-known-SHA verification against the upstream history
- Per-commit author/email/sign visibility

If an attacker compromises GitHub's serving infrastructure, our DNS, or the upstream branch (e.g., force-pushes a poisoned commit), the content-level safety checks listed below are the only thing standing between bad upstream content and our grid. They have to carry that weight without help. Hence the paranoid posture (every flag is block) and the prominence of the future git-collector-base abstraction in [Future Work](#future-work) — that gets the provenance chain back.

#### Block-class checks

All flags abort the run before `submit_collector_grift` is called. The collector records each flag via `tap_cares.results.record_error` so the failing job's `results["error"]` carries the full structured detail.

| Code | Trigger |
| --- | --- |
| `SCHEMA_DRIFT` | Fetched JSON fails validation against the pinned schema. |
| `UNKNOWN_FIELD` | Fetched content contains a key not declared in the pinned schema's `properties`. |
| `STRUCTURAL_CAP` | Catalog exceeds size caps: total bytes > 10 MiB, > 20 themes, > 100 indicators per theme, > 100 KiB per string field, > 200 items per array. |
| `CHARACTER_CLASS` | Any string field contains a Unicode BiDi override character or a control character other than `\t` / `\n`. |
| `DENYLIST_PHRASE` | A string field matches the safety denylist (prompt-injection heuristics). Promoted from warn → block per the paranoid-posture decision. |
| `OUTLIER_STRING_LENGTH` | A string field is dramatically longer than the field's historical norm. Promoted from warn → block per the paranoid-posture decision. |
| `MASS_DELETION` | Diff would deprecate > 10% of live indicators in one run (see `req-fedramp-20x-ksi-collector-mass-deletion`). |
| `UPSTREAM_OVERSIZED` | Fetch body > 10 MiB (see `req-fedramp-20x-ksi-collector-fetch`). |
| `UPSTREAM_BAD_CONTENT_TYPE` | Non-JSON content-type (see `req-fedramp-20x-ksi-collector-fetch`). |

#### Dropped checks

Provenance / commit-history checks from the old refresh tool that have no runtime analogue under HTTPS fetch:

| Code | Why dropped |
| --- | --- |
| `INTEGRITY_REWIND` | No submodule pointer to compare against; we fetch live state, not a pointer advance. Comes back with the future git collector base class. |
| `ORIGIN_MISMATCH` (git URL) | We're fetching from a pinned HTTPS URL; the host/path *is* the origin check. Comes back with the future git collector base class. |
| `commit_author_drift` | No commit log in a live JSON fetch. Comes back with the future git collector base class. |
| `low_quality_commit_message` | Same. |
| `signed` / `verified` checks | Same. |

The safety denylist content moves from `skills/refresh-ksi-catalog/safety/denylist.json` to `plugins/fedramp_20x_ksi/collectors/safety/denylist.json` byte-for-byte.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-safety-1 | All Flags Block | Proposed | Every flag in the table above is block-class. There is no warn tier in v0. | |
| req-fedramp-20x-ksi-collector-safety-2 | Block Halts Before Submission | Proposed | Any block flag aborts the run before `submit_collector_grift` is called. No partial submission, no half-imported state. | |
| req-fedramp-20x-ksi-collector-safety-3 | Structured Error Capture | Proposed | The collector records every flag via `tap_cares.results.record_error(job, site, code, message, context=...)`. The failing `CollectionJob.results["error"]` carries one entry per flag raised. | |
| req-fedramp-20x-ksi-collector-safety-4 | Terminal Summary | Proposed | The collector sets `CollectionJob.error_summary` to a one-line description of the highest-severity flag for at-a-glance display. | |
| req-fedramp-20x-ksi-collector-safety-5 | Denylist Ported | Proposed | The existing safety denylist content is moved into the plugin's `collectors/safety/` directory byte-for-byte. | |
| req-fedramp-20x-ksi-collector-safety-6 | Trust Model Documented | Proposed | The spec explicitly states the HTTPS-only trust model and its limitations relative to a future git-backed fetch. | |
| req-fedramp-20x-ksi-collector-safety-7 | Dropped Checks Documented | Proposed | CI-specific checks (integrity rewind, origin URL, commit metadata) are documented as not-applicable to v0 HTTPS fetch and named as recovered-by the future git collector base. | |

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
  }
}
```

The batch's `description_json.data` carries only **what was successfully collected and submitted**: source provenance and change counts. There is no `safety` field — every safety check is block-class (`req-fedramp-20x-ksi-collector-safety-1`), so a successful submission means *no* safety flags fired. Failed runs produce no batch at all; the structured failure detail lives in `CollectionJob.results["error"]` instead.

Dropped fields vs the old `wave-v0`:

- `commits[]` — no commit log in HTTPS fetch. Returns when the future git collector base lands (see [Future Work](#future-work)).
- `wave.index` / `wave.filename` / `wave.is_initial` — collection runs aren't a numbered wave sequence.
- `wave.authored_at` / `wave.authored_by` — `CollectionJob.started_at` and the run's caller-context already carry this.
- `safety.review_required` / `safety.flags` — superseded by the per-flag block model plus `CollectionJob.results["error"]`.

The batch entity_id is a fresh UUIDv7 per run. Individual theme/indicator entity_ids are the same deterministic UUIDv5 values as today (`req-fedramp-20x-ksi-collector-pin-3`), so GRIFT upsert lands changes on the existing entities rather than creating duplicates.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-grift-1 | One Batch Per Run | Proposed | Non-empty runs submit exactly one GRIFT batch via `submit_collector_grift`. | |
| req-fedramp-20x-ksi-collector-grift-2 | collection-v0 Format | Proposed | The batch's `description_json.format` is `tap.fedramp_20x_ksi.collection-v0`. | |
| req-fedramp-20x-ksi-collector-grift-3 | Source Provenance | Proposed | `description_json.data.source` records URL, fetched_at, content_sha256, byte_size, and the upstream `rules_version` field. | |
| req-fedramp-20x-ksi-collector-grift-4 | Change Counts | Proposed | `description_json.data.changes` reports new/modified/deprecated counts for themes and indicators, plus catalog size before/after and deletion ratio. | |
| req-fedramp-20x-ksi-collector-grift-5 | No Safety Field | Proposed | `description_json.data` has no `safety` field. With every safety check block-class, a successful submission means no flags fired; failed runs produce no batch. Structured failure detail lives in `CollectionJob.results["error"]`. | |
| req-fedramp-20x-ksi-collector-grift-6 | Deterministic Entity IDs | Proposed | Theme and indicator entity_ids are stable UUIDv5 derivations; re-runs upsert in place. | |
| req-fedramp-20x-ksi-collector-grift-7 | Pinned Schema For description_json | Proposed | A JSON Schema for `collection-v0.data` ships at `plugins/fedramp_20x_ksi/collectors/pinned/collection-v0.schema.json` and the collector validates its own output against it before submission. | |
| req-fedramp-20x-ksi-collector-grift-8 | Change-Only Submission | Proposed | The batch contains only entities classified as `new`, `modified`, or `removed` (deprecation-via-modification) — never `unchanged`. v0 does not bump observation timestamps on unchanged entities; "still observed" semantics are a future investigation (see [Future Work](#future-work)). | |

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

The KSI collector uses the existing `CollectionJob` lifecycle states (`READY`/`RUNNING`/`FAILED`/`SUCCESSFUL`) and the structured `results` field defined in `req-tap-cares-collector-job-model` (the `info` / `warn` / `error` buckets with four-field entries). No KSI-specific state, edge type, or metadata field. All structured failure surfacing flows through `record_error` from `tap_cares.results`; all run-level successes flow through `record_info`.

#### Successful run (no changes)

- `status = SUCCESSFUL`
- `error_summary = ""`
- `grift_batches = {"imported": [], "skipped": []}`
- `results["info"]` contains entries for: `RUN_STARTED`, `UPSTREAM_FETCHED`, `DIFF_EMPTY`, `RUN_COMPLETED`.
- `results["error"]` empty.

#### Successful run (changes submitted)

- `status = SUCCESSFUL`
- `error_summary = ""`
- `grift_batches.imported` contains the single batch entity_id this run produced.
- `results["info"]` contains entries for: `RUN_STARTED`, `UPSTREAM_FETCHED`, `DIFF_COMPUTED` (with counts in context), `GRIFT_SUBMITTED` (with batch entity_id in context), `RUN_COMPLETED`.
- `results["error"]` empty.

#### Failed run

- `status = FAILED`
- `error_summary` carries the one-line description of the highest-severity block flag (collector-set; renders in admin lists, job headers).
- `grift_batches = {"imported": [], "skipped": []}` — nothing reached the grid.
- `results["error"]` contains one entry per flag raised, each with its own `site` UUIDv7, `code`, `message`, and `context` (the dict of relevant counts, fragments, or paths into the source document — collector's call what's useful for the investigator).
- `results["info"]` may contain partial-run breadcrumbs (`RUN_STARTED`, `UPSTREAM_FETCHED`) for runs that got past initial steps before failing.

#### Result event vocabulary (v0)

| Level | Code | When |
| --- | --- | --- |
| `info` | `RUN_STARTED` | First action of `run()`. Context: collector entity_id, job entity_id. |
| `info` | `UPSTREAM_FETCHED` | After successful HTTPS GET + content-type / size checks. Context: URL, byte_size, content_sha256, rules_version. |
| `info` | `DIFF_COMPUTED` | After diff produces a non-empty changeset. Context: counts (new / modified / deprecated for themes and indicators). |
| `info` | `DIFF_EMPTY` | Diff produces no changes; no GRIFT submission to follow. |
| `info` | `GRIFT_SUBMITTED` | After `submit_collector_grift` returns successfully. Context: batch entity_id, imported count. |
| `info` | `RUN_COMPLETED` | Last action of `run()`. Context: terminal status. |
| `error` | `SCHEMA_DRIFT` | Pinned-schema validation failed. Context: validator error path + message. |
| `error` | `UNKNOWN_FIELD` | Upstream contains a key not in pinned schema. Context: path. |
| `error` | `STRUCTURAL_CAP` | Size cap breached. Context: which cap, observed value, limit. |
| `error` | `CHARACTER_CLASS` | Disallowed character. Context: path, character codepoint. |
| `error` | `DENYLIST_PHRASE` | Denylist match. Context: path, phrase fragment. |
| `error` | `OUTLIER_STRING_LENGTH` | Anomalous length. Context: path, observed length, historical norm. |
| `error` | `MASS_DELETION` | Deprecation ratio > threshold. Context: ratio, deprecated count, live count. |
| `error` | `UPSTREAM_OVERSIZED` | Fetch body > 10 MiB. Context: byte_size. |
| `error` | `UPSTREAM_BAD_CONTENT_TYPE` | Wrong content-type. Context: observed content_type. |
| `error` | `UPSTREAM_FETCH_FAILED` | Network / HTTP error. Context: exception class, message. |

This vocabulary is the v0 KSI collector contract; new collectors emit their own codes under the same shape.

The `warn` bucket is unused by the v0 KSI collector — every safety flag is block-class. The bucket exists at the `tap_cares` level so future collectors with genuinely non-fatal events can populate it without schema churn.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-job-result-1 | No New Status States | Proposed | The KSI collector uses only the existing `READY`/`RUNNING`/`FAILED`/`SUCCESSFUL` states. | |
| req-fedramp-20x-ksi-collector-job-result-2 | Successful Empty | Proposed | A run that detects no changes still succeeds; `grift_batches.imported` is empty; `results["info"]` records `DIFF_EMPTY`. | |
| req-fedramp-20x-ksi-collector-job-result-3 | Block → FAILED | Proposed | Any block flag fails the job. `record_error` is called for every flag raised; `error_summary` is set to the highest-severity flag's message. | |
| req-fedramp-20x-ksi-collector-job-result-4 | Vocabulary Documented | Proposed | The v0 event vocabulary above is the contract; new codes require updating the spec. | |
| req-fedramp-20x-ksi-collector-job-result-5 | Site UUIDs Unique Per Callsite | Proposed | Each `record_*` call in the KSI collector code has a hardcoded UUIDv7 `site` value; the repo-wide uniqueness test (`req-tap-cares-collector-job-model-15`) covers KSI callsites. | |
| req-fedramp-20x-ksi-collector-job-result-6 | Warn Bucket Unused | Proposed | The KSI collector emits no `warn`-level entries in v0; all safety flags are block-class. | |
| req-fedramp-20x-ksi-collector-job-result-7 | Standard Observability | Proposed | The job is queryable through standard `tap_cares` surfaces; no KSI-specific reporting plumbing. | |

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
   - `denylist_block.json` — variant containing a denylist phrase (block-class in v0).

2. **Live-fetch integration test** (slow, requires network). Gated by a pytest marker (`@pytest.mark.live_fetch`) so it can be opted out of in CI by default. Verifies the real HTTPS fetch round-trips and parses, but does not assert on the resulting diff (since upstream content changes).

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-test-strategy-1 | Fixture-Injected Unit Tests | Proposed | Unit tests cover happy path and every block flag by overriding `fetch_upstream()` with fixtures. | |
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
| `req-fedramp-20x-ksi-reference` | `Revised` | Catalog seed ships as a single GRIFT file (see below); the "catalog content distributes as a sequence of dated waves" contract is dropped. The wave cadence dies; the seed survives, singular. |

Models (`ksi_theme`, `ksi_indicator`), edges (`CONTAINS_INDICATOR`), icons, dimensions, status, classes, controls, NIST crosswalk plans — all unaffected.

#### Seed file

The plugin continues to ship a current-time catalog snapshot for fresh-install cold-start. The shape changes from a dated-wave cadence to **a single seed file**:

- Filename: `plugins/fedramp_20x_ksi/grift/ksi-seed.grift.json` (singular, undated).
- Contents: the current catalog as a GRIFT batch with deterministic theme/indicator entity_ids (same UUIDv5 derivation as the collector uses; `req-fedramp-20x-ksi-collector-pin-3`).
- Bundled with the plugin, committed to the plugin repo.
- Imported on fresh installs via `import_plugin_grift fedramp_20x_ksi`; subsequent imports skip per GRIFT's already-imported guard.

This preserves the offline / no-GitHub install path. Once the plugin is up, the collector takes over for updates. The seed gets refreshed in place (filename stays the same) when a maintainer decides to bump it — initially manually, eventually via a future emitter that rebakes from current grid state.

The previously-shipped `ksi-initial-YYYY-MM-DD.grift.json` and any `ksi-wave-YYYY-MM-DD.grift.json` files are deleted in this phase. The on-grid `Collector` seed (a separate small GRIFT file) and `dimension.grift.json` survive untouched.

#### Database state on existing dev installs

Per direction from spec review: the existing data in any developer's local TAP grid can be wiped and re-collected from a fresh KSI collector run, or re-seeded via `import_plugin_grift` followed by a collector run. No migration of historical wave provenance.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-deprecation-1 | Code Removed | Proposed | `skills/refresh-ksi-catalog/`, the submodule, the nightly GitHub Action, and any manifest references are deleted in this phase. | |
| req-fedramp-20x-ksi-collector-deprecation-2 | Content Migrated | Proposed | Pinned schema, UUID namespace, and denylist move byte-exact into `plugins/fedramp_20x_ksi/collectors/`. | |
| req-fedramp-20x-ksi-collector-deprecation-3 | Waves Replaced By Seed | Proposed | Existing `ksi-initial-*.grift.json` and `ksi-wave-*.grift.json` files are deleted. A single `ksi-seed.grift.json` (current-time snapshot) replaces them. The on-grid `Collector` seed and `dimension.grift.json` survive. | |
| req-fedramp-20x-ksi-collector-deprecation-4 | v0 Spec Status Sync | Proposed | `req-fedramp-20x-ksi-refresh`, `-wave-schema`, `-safety`, and `-reference` are updated in `spec-fedramp-20x-ksi-v0.md` per the table above, with cross-references to this spec. | |
| req-fedramp-20x-ksi-collector-deprecation-5 | Seed Singular And Undated | Proposed | The shipped seed file uses the fixed filename `ksi-seed.grift.json`; refreshes overwrite in place. Dated filenames are no longer used. | |

---

### Future Work
----
RID: `req-fedramp-20x-ksi-collector-future`
Status: `Proposed`

Items intentionally deferred:

1. **Git collector base class.** The biggest deferred item, and the one we expect to land soonest. A `tap_cares.collectors.GitCollectorBase` would subclass `CollectorBase` and bake in the provenance posture that HTTPS-only fetch cannot provide. Concrete scope when it ships:

   - Pinned origin (URL + branch) check, replacing today's pinned-URL check.
   - Persistent shallow-clone cache lifecycle (`git clone --depth=1` first run; `git fetch` thereafter) in a tap_cares-owned cache dir (probably configurable via a `TAP_CARES_CACHE_DIR` setting).
   - `git merge-base --is-ancestor` rewind protection. Last-integrated SHA is read from the most recent successful `CollectionJob.description_json.data.source.commit_to` — the grid is the state store; no on-disk manifest needed.
   - Commit metadata extraction (`sha`, `date`, `author_name`, `author_email`, `signed`, `verified`, `message_first_line`).
   - A subclass hook so the KSI collector says *"my source document is `fedramp-consolidated-rules.json` in this checkout"* without the parent class needing to know about FedRAMP.

   Migration impact when this lands: the KSI collector resubclasses `GitCollectorBase` instead of `CollectorBase`; the dropped safety checks (`INTEGRITY_REWIND`, `ORIGIN_MISMATCH`, `COMMIT_AUTHOR_DRIFT`, signing checks) come back as block-class; `description_json.data.commits[]` returns; the HTTPS trust-model caveat in `req-fedramp-20x-ksi-collector-safety` becomes obsolete.

2. **Scheduled refresh.** Once `tap_cares` ships a scheduler (`req-tap-cares-v0-scheduler`), the KSI collector becomes the first concrete consumer. v0 KSI collector runs are triggered manually (Django shell, management command, or admin button).

3. **Emitter loop back to FedRAMP/rules.** When `tap_cares` emitters land, a complementary `KSIEmitter` could push local-instance edits back to the FedRAMP/rules repo as PRs, making a TAP installation the canonical authoring path. The collector's `description_json.data.source` already records the inverse direction; symmetry with an emitter is intentional.

4. **"Touch entity" primitive in tap_grid.** v0 KSI does change-only upsert — unchanged entities are left strictly alone. A future `touch_entity(entity_id)` service-layer primitive on tap_grid would let the collector bump `Entity.updated_at` on unchanged entities *without* generating a history row, enabling an "as of last run, still observed" semantic without the history-table noise that "upsert everything every run" would cause. Investigation belongs in `tap_grid` spec backlog, not here — the right home is the GRIFT / Entity spec, not a plugin spec.

5. **Delete semantics in GRIFT.** Current `tap_grid` GRIFT importer has no explicit delete operation; deprecation-via-modification fills the gap. A proper delete (with entity_id list + reasons) would let the catalog actually shrink rather than accumulate `deprecated` entries forever. Tracked in `tap_grid` spec backlog; the KSI collector adopts it if/when it ships.

6. **Live-fetch CI gate.** A nightly CI job that runs the `@pytest.mark.live_fetch` test against real upstream would catch upstream-shape changes early. Not a v0 must.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-fedramp-20x-ksi-collector-future-1 | Named Successors | Proposed | The above six future items are named and cross-referenced to their owning specs / backlog items. | |
| req-fedramp-20x-ksi-collector-future-2 | Git Collector Base Scope Concrete | Proposed | The git-collector-base item names specific responsibilities (origin pin, clone cache, ancestor verification, commit metadata) so the future implementer has a clear scope. | |

---

## Status Vocabulary

Same as `spec-fedramp-20x-ksi-v0.md`. Statuses used in this spec at draft time: `Proposed`.

## Cross-References

- `tap_cares/specs/spec-tap-cares-v0.md` — runtime collector / GRIFT-import architecture this spec builds on.
- `tap_cares/specs/spec-tap-cares-collector.md` — `CollectorBase`, `collector_registry`, `submit_collector_grift`, `CollectionJob` contracts.
- `plugins/fedramp_20x_ksi/specs/spec-fedramp-20x-ksi-v0.md` — catalog modeling spec; this collector spec deprecates its refresh-related sections (see `req-fedramp-20x-ksi-collector-deprecation`).
