---
name: refresh-ksi-catalog
description: Fetch the current FedRAMP 20x KSI catalog and emit the next GRIFT wave for this plugin. Authorship tooling intended for the plugin maintainer or CI; not for operators running TAP installations.
disable-model-invocation: true
---

# Refresh FedRAMP 20x KSI Catalog (Placeholder)

This skill is a placeholder. Full design and implementation are deferred to a dedicated session.

See `specs/spec-fedramp-20x-ksi-v0.md` `req-fedramp-20x-ksi-refresh` for the intended contract. The skill's responsibilities are:

- fetch the current FedRAMP 20x KSI catalog from the authoritative source
- reconstruct the catalog state implied by existing waves in `grift/`
- diff current source against that reconstructed state
- emit `grift/ksi-wave-YYYY-MM-DD.grift.json` (or `ksi-initial-YYYY-MM-DD.grift.json` if no prior waves exist) capturing additions, modifications, and deprecations
- produce stable deterministic entity IDs across runs
- mark indicators missing from source as `status: deprecated` rather than deleting them
- emit no wave file when source matches the reconstructed state

Intended automation: a GitHub Action in the plugin repo runs this skill on a nightly schedule, opens a PR against `main` when a wave is produced, and a human reviewer merges.

Design work still required:

- source URL(s) and fetch protocol
- machine-readable catalog parsing
- diff algorithm and wave file schema beyond GRIFT base shape
- deterministic UUID derivation (likely UUIDv5 from a plugin-scoped namespace + `code`)
- how to handle source format changes (FedRAMP's 2025-11-18 rename is recent precedent)
