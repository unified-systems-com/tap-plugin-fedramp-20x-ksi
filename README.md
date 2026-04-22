# tap-plugin-fedramp-20x-ksi

TAP plugin modeling the [FedRAMP 20x Key Security Indicators](https://www.fedramp.gov/docs/20x/key-security-indicators/) catalog as graph nodes — themes and individual indicators — so evidence, observations, and compliance posture can attach to them in TAP.

## What's in the catalog

**Themes** — top-level groupings of related security outcomes.

| Code | Theme |
| --- | --- |
| KSI-ABF | Authorization by FedRAMP |
| KSI-CHM | Change Management |
| KSI-CNA | Cloud Native Architecture |
| KSI-CYE | Cybersecurity Education |
| KSI-IAM | Identity and Access Management |
| KSI-INC | Incident Response |
| KSI-MLA | Monitoring, Logging, and Auditing |
| KSI-POI | Policy and Inventory |
| KSI-RCP | Recovery Planning |
| KSI-SVC | Service Configuration |
| KSI-SCR | Supply Chain Risk |

**Indicators** — individual measurable security outcomes within a theme (e.g. KSI-IAM-01). Approximately 56 apply at the Low impact baseline, 61 at Moderate. Each indicator carries source-faithful validation criteria, lifecycle status (`draft`/`published`/`deprecated`), and the baselines it applies to.

FedRAMP renamed these fields on 2025-11-18: what they now call a "theme" was previously an "indicator", and what they now call an "indicator" was previously a "requirement". This plugin uses the current vocabulary.

## TAP surfaces

**Models:** `ksi_theme`, `ksi_indicator`

**Edges:** `CONTAINS_INDICATOR` (theme → indicator)

**Default dimensions:** `{"compliance": "fedramp-20x"}` on every node and edge

## Installation

Add as a submodule from the TAP repo root:

```bash
git submodule add https://github.com/notgeorge/tap-plugin-fedramp-20x-ksi.git plugins/fedramp_20x_ksi
```

Then add `"plugins.fedramp_20x_ksi"` to `INSTALLED_APPS` and run migrations:

```bash
docker compose exec web uv run python manage.py migrate
```

## Validation

From the TAP repo root, structure-level validation (runs without Django):

```bash
docker compose exec web uv run python -m tap_plugins.validate_plugin plugins/fedramp_20x_ksi --strict
```

Loads and runs validation (requires the plugin in `INSTALLED_APPS` and migrations applied):

```bash
docker compose exec web uv run python manage.py validate_plugin plugins/fedramp_20x_ksi --level runs
```

## Catalog distribution

The plugin distributes catalog content as versioned GRIFT waves in `grift/`. Each wave is a dated batch: `ksi-initial-YYYY-MM-DD.grift.json` for the first, `ksi-wave-YYYY-MM-DD.grift.json` for subsequent additions, modifications, and deprecations. Applied in order, waves reconstruct the current catalog.

The `skills/refresh-ksi-catalog/` skill is authorship tooling that generates the next wave from the current FedRAMP 20x source. It is intended for the plugin maintainer or a CI agent, not for operators running TAP installations. Design is deferred; see `specs/spec-fedramp-20x-ksi-v0.md` for the intended contract.

v0 ships no wave files yet.

## Specification

See [`specs/spec-fedramp-20x-ksi-v0.md`](specs/spec-fedramp-20x-ksi-v0.md) for the authoritative design — requirements, model field contracts, edge direction, GRIFT wave conventions, icon contract, and non-goals.
