#!/usr/bin/env python3
"""refresh-ksi-catalog — deterministic tool for ingesting FedRAMP 20x KSI catalog updates.

Security posture: the upstream source is not trusted. This tool treats every
value from upstream as data, never as instructions. It never fetches URLs
found in source content, never executes code based on source content, and
never follows references beyond the pinned source submodule.

See specs/spec-fedramp-20x-ksi-v0.md req-fedramp-20x-ksi-refresh.

Exit codes:
    0 — refresh succeeded (wave emitted or no-op)
    1 — refresh blocked by a safety flag
    2 — dependency missing or tool misconfiguration
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:
    print(
        "ERROR: jsonschema not installed. Run: pip install jsonschema", file=sys.stderr
    )
    sys.exit(2)


# Layout ----------------------------------------------------------------------

SKILL_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SKILL_DIR.parent.parent
UPSTREAM_DIR = SKILL_DIR / "upstream"
PINNED_DIR = SKILL_DIR / "pinned"
SAFETY_DIR = SKILL_DIR / "safety"
STATE_DIR = SKILL_DIR / "state"
GRIFT_DIR = PLUGIN_ROOT / "grift"

AUTHORED_BY = "refresh-ksi-catalog@v0"

# Caps — per req-fedramp-20x-ksi-refresh
MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_THEMES = 20
MAX_INDICATORS_PER_THEME = 100
MAX_STRING_LEN = 100 * 1024
MAX_ARRAY_LEN = 200

# Regexes
THEME_CODE_RE = re.compile(r"^KSI-[A-Z]{3}$")
INDICATOR_CODE_RE = re.compile(r"^KSI-[A-Z]{3}-[A-Z0-9]{3}$")

# Character class gates
BIDI_OVERRIDE_RE = re.compile(r"[‪-‮⁦-⁩]")
BAD_CONTROL_RE = re.compile(r"[\x00-\x08\x0B-\x1F\x7F]")

MASS_DELETION_RATIO = 0.10

WAVE_FORMAT = "tap.fedramp_20x_ksi.wave-v0"


# Flag types ------------------------------------------------------------------


@dataclass
class Flag:
    severity: str  # "block" | "warn" | "info"
    code: str
    detail: str


@dataclass
class FlagBag:
    flags: list[Flag] = field(default_factory=list)

    def add(self, severity: str, code: str, detail: str) -> None:
        self.flags.append(Flag(severity=severity, code=code, detail=detail))

    @property
    def has_block(self) -> bool:
        return any(f.severity == "block" for f in self.flags)

    @property
    def has_warn(self) -> bool:
        return any(f.severity == "warn" for f in self.flags)

    def as_list(self) -> list[dict[str, str]]:
        return [
            {"severity": f.severity, "code": f.code, "detail": f.detail}
            for f in self.flags
        ]


# Git helpers — operate on upstream submodule --------------------------------


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git"] + args, cwd=cwd, check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip()}"
        )
    return result.stdout.rstrip("\n")


def upstream_head_sha() -> str:
    return _git(["rev-parse", "HEAD"], UPSTREAM_DIR)


def upstream_remote_url() -> str:
    return _git(["config", "--get", "remote.origin.url"], UPSTREAM_DIR)


def is_ancestor(maybe_ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", maybe_ancestor, descendant],
        cwd=UPSTREAM_DIR,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _ensure_reachable(sha: str) -> None:
    """Unshallow the submodule if the given SHA is unreachable."""
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=UPSTREAM_DIR,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        _git(["fetch", "--unshallow"], UPSTREAM_DIR)


def upstream_commits_between(since: str | None, to: str) -> list[dict[str, Any]]:
    """Return commit metadata for the range (since, to], or everything up to `to` if None."""
    if since is not None:
        _ensure_reachable(since)
    range_arg = to if since is None else f"{since}..{to}"
    output = _git(
        [
            "log",
            range_arg,
            "--no-merges",
            "--pretty=format:%H%x1f%cI%x1f%an%x1f%ae%x1f%G?%x1f%s",
        ],
        UPSTREAM_DIR,
    )
    commits = []
    for line in output.split("\n"):
        if not line:
            continue
        parts = line.split("\x1f")
        if len(parts) < 6:
            continue
        sha, date, name, email, gpg, subject = parts
        commits.append(
            {
                "sha": sha,
                "date": date,
                "author_name": name,
                "author_email": email,
                "signed": gpg != "N",
                "verified": gpg == "G",
                "message_first_line": subject[:200],
            }
        )
    return commits


# Pinned asset loaders --------------------------------------------------------


def load_source_origin() -> dict[str, Any]:
    return json.loads((PINNED_DIR / "source_origin.json").read_text())


def load_pinned_schema() -> dict[str, Any]:
    return json.loads((PINNED_DIR / "source_schema.json").read_text())


def load_wave_schema() -> dict[str, Any]:
    return json.loads((PINNED_DIR / "wave-v0.schema.json").read_text())


def load_uuid_namespace() -> uuid.UUID:
    return uuid.UUID((PINNED_DIR / "uuid_namespace.txt").read_text().strip())


def load_safety_config() -> dict[str, Any]:
    doc = json.loads((SAFETY_DIR / "denylist.json").read_text())
    return doc.get("rules", {})


def load_state_manifest() -> dict[str, Any]:
    path = STATE_DIR / "source-manifest.json"
    if not path.exists():
        return {
            "last_integrated_sha": None,
            "last_integrated_date": None,
            "last_integrated_file_sha256": None,
            "waves": [],
        }
    doc = json.loads(path.read_text())
    doc.pop("$description", None)
    return doc


def save_state_manifest(manifest: dict[str, Any]) -> None:
    path = STATE_DIR / "source-manifest.json"
    out = {
        "$description": "Tracks the last-integrated upstream SHA and per-wave metadata. "
        "Written exclusively by refresh.py; do not hand-edit.",
        **manifest,
    }
    path.write_text(json.dumps(out, indent=2) + "\n")


# Integrity and validation ----------------------------------------------------


def check_origin(origin: dict[str, Any], bag: FlagBag) -> None:
    actual = upstream_remote_url()
    accepted = [origin["expected_url"]] + origin.get("expected_url_aliases", [])
    if actual not in accepted:
        bag.add(
            "block",
            "ORIGIN_MISMATCH",
            f"Submodule URL '{actual}' not in pinned expected set",
        )


def check_history_integrity(
    prior_sha: str | None, current_sha: str, bag: FlagBag
) -> None:
    if prior_sha is None:
        return
    if prior_sha == current_sha:
        return
    _ensure_reachable(prior_sha)
    if not is_ancestor(prior_sha, current_sha):
        bag.add(
            "block",
            "INTEGRITY_REWIND",
            f"Prior SHA {prior_sha[:7]} is not an ancestor of current {current_sha[:7]}",
        )


def check_source_files(bag: FlagBag) -> tuple[bytes, bytes] | tuple[None, None]:
    origin = load_source_origin()
    src_path = UPSTREAM_DIR / origin["source_json_path"]
    schema_path = UPSTREAM_DIR / origin["source_schema_path"]
    if not src_path.exists():
        bag.add(
            "block",
            "SOURCE_MISSING",
            f"{origin['source_json_path']} missing from upstream",
        )
        return None, None
    if not schema_path.exists():
        bag.add(
            "block",
            "SOURCE_MISSING",
            f"{origin['source_schema_path']} missing from upstream",
        )
        return None, None
    src_bytes = src_path.read_bytes()
    schema_bytes = schema_path.read_bytes()
    if len(src_bytes) > MAX_SOURCE_BYTES:
        bag.add(
            "block",
            "SIZE_CAP",
            f"Source JSON {len(src_bytes)} bytes exceeds cap {MAX_SOURCE_BYTES}",
        )
    return src_bytes, schema_bytes


def check_schema_drift(actual_schema_bytes: bytes, bag: FlagBag) -> None:
    pinned = (PINNED_DIR / "source_schema.json").read_bytes()
    if actual_schema_bytes != pinned:
        bag.add(
            "block",
            "SCHEMA_DRIFT",
            "Upstream schema bytes differ from pinned schema. Human review required before advancing.",
        )


def validate_against_pinned_schema(source: dict[str, Any], bag: FlagBag) -> None:
    try:
        jsonschema.validate(source, load_pinned_schema())
    except jsonschema.ValidationError as exc:
        bag.add(
            "block",
            "SCHEMA_VALIDATION",
            f"Source fails pinned schema: {exc.message[:200]}",
        )


def check_structural_caps(source: dict[str, Any], bag: FlagBag) -> None:
    ksi = source.get("KSI", {})
    if len(ksi) > MAX_THEMES:
        bag.add("block", "SIZE_CAP", f"{len(ksi)} themes exceed cap {MAX_THEMES}")
    for code, theme in ksi.items():
        indicators = theme.get("indicators", {})
        if len(indicators) > MAX_INDICATORS_PER_THEME:
            bag.add(
                "block",
                "SIZE_CAP",
                f"Theme {code} has {len(indicators)} indicators > cap {MAX_INDICATORS_PER_THEME}",
            )


def walk_strings(obj: Any, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def check_character_classes(source: dict[str, Any], bag: FlagBag) -> None:
    for path, text in walk_strings(source):
        if BIDI_OVERRIDE_RE.search(text):
            bag.add(
                "block", "CHARACTER_CLASS", f"{path}: contains BiDi override character"
            )
            return
        if BAD_CONTROL_RE.search(text):
            bag.add(
                "block",
                "CHARACTER_CLASS",
                f"{path}: contains control char outside \\t\\n",
            )
            return
        if len(text) > MAX_STRING_LEN:
            bag.add("block", "SIZE_CAP", f"{path}: string length {len(text)} > cap")
            return


def check_code_formats(source: dict[str, Any], bag: FlagBag) -> None:
    # Source keys inside "KSI" are 3-letter short names; the canonical KSI code
    # is the theme's "id" field. Check that instead.
    for theme_key, theme in source.get("KSI", {}).items():
        theme_code = theme.get("id", "")
        if not THEME_CODE_RE.match(theme_code):
            bag.add(
                "warn",
                "CODE_FORMAT",
                f"Theme at key '{theme_key}' has id '{theme_code}' violating regex",
            )
        for ind_code in theme.get("indicators", {}):
            if not INDICATOR_CODE_RE.match(ind_code):
                bag.add(
                    "warn", "CODE_FORMAT", f"Indicator code '{ind_code}' violates regex"
                )


# Denylist heuristics ---------------------------------------------------------


def run_denylist_on_ksi(
    source: dict[str, Any], safety: dict[str, Any], bag: FlagBag
) -> None:
    ksi_section = source.get("KSI", {})
    for rule_name, rule in safety.items():
        if not isinstance(rule, dict):
            continue
        if rule_name == "low_quality_commit_message":
            continue  # applied to commit messages, not source text
        severity = rule.get("severity")
        code = rule.get("code")
        patterns = rule.get("patterns", [])
        if not (severity and code and patterns):
            continue
        for path, text in walk_strings(ksi_section):
            if rule_name == "url_scheme_warn" and path.endswith(".reference_url"):
                continue
            for pat in patterns:
                try:
                    if re.search(pat, text, re.IGNORECASE):
                        snippet = text[:80].replace("\n", "\\n")
                        bag.add(
                            severity, code, f"{path}: matches {pat!r} near {snippet!r}"
                        )
                        break
                except re.error:
                    # Malformed pattern in denylist — skip silently; should be caught in dev
                    continue


# Commit metadata checks ------------------------------------------------------


def check_commits(
    commits: list[dict[str, Any]],
    origin: dict[str, Any],
    safety: dict[str, Any],
    bag: FlagBag,
) -> None:
    domains = set(origin.get("expected_committer_email_domains", []))
    msg_rules = safety.get("low_quality_commit_message", {})
    min_len = msg_rules.get("min_length", 10)
    patterns = msg_rules.get("patterns", [])
    for c in commits:
        if not c["signed"]:
            bag.add("info", "COMMIT_UNSIGNED", f"{c['sha'][:7]} unsigned")
        email = c["author_email"] or ""
        domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
        if domain and domain not in domains:
            bag.add(
                "warn",
                "COMMITTER_DOMAIN",
                f"{c['sha'][:7]} committer email '{email}' outside expected domains",
            )
        msg = c["message_first_line"].strip()
        if len(msg) < min_len:
            bag.add(
                "warn",
                "COMMIT_MESSAGE_QUALITY",
                f"{c['sha'][:7]} message too short: {msg!r}",
            )
            continue
        for pat in patterns:
            try:
                if re.match(pat, msg, re.IGNORECASE):
                    bag.add(
                        "warn",
                        "COMMIT_MESSAGE_QUALITY",
                        f"{c['sha'][:7]} message low-quality: {msg!r}",
                    )
                    break
            except re.error:
                continue


# Prior state reconstruction --------------------------------------------------


def reconstruct_prior_state() -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {"themes": {}, "indicators": {}}
    if not GRIFT_DIR.exists():
        return state
    waves = sorted(
        p
        for p in GRIFT_DIR.iterdir()
        if p.suffix == ".json" and p.name.startswith(("ksi-initial-", "ksi-wave-"))
    )
    for wave in waves:
        try:
            doc = json.loads(wave.read_text())
        except Exception:
            continue
        for batch in doc.get("batches", []):
            for node in batch.get("nodes", []):
                entity_type = node.get("entity", {}).get("entity_type")
                ndata = node.get("node", {})
                code = ndata.get("code")
                if not code:
                    continue
                if entity_type == "ksi_theme":
                    state["themes"][code] = ndata
                elif entity_type == "ksi_indicator":
                    state["indicators"][code] = ndata
    return state


# Diff and ID derivation ------------------------------------------------------


def ns_uuid(namespace: uuid.UUID, kind: str, key: str) -> str:
    return str(uuid.uuid5(namespace, f"{kind}:{key}"))


def derive_theme_state(theme: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": theme.get("id", ""),
        "name": theme.get("name", ""),
        "short_name": theme.get("short_name", ""),
        "web_name": theme.get("web_name", ""),
        "description": "",
    }


def indicator_classes(indicator: dict[str, Any]) -> list[str]:
    varies = indicator.get("varies_by_class")
    if isinstance(varies, dict):
        return sorted(k for k in varies if k in ("a", "b", "c", "d"))
    # Direct statement — default applicability (b/c/d) until FRR mapping lands.
    return ["b", "c", "d"]


def derive_indicator_state(code: str, indicator: dict[str, Any]) -> dict[str, Any]:
    varies = indicator.get("varies_by_class")
    class_variants = varies if isinstance(varies, dict) else None
    statement = indicator.get("statement", "") or ""
    return {
        "code": code,
        "name": indicator.get("name", ""),
        "description": statement if class_variants is None else "",
        "classes": indicator_classes(indicator),
        "class_variants": class_variants,
        "controls": indicator.get("controls", []) or [],
        "updated_log": indicator.get("updated", []) or [],
        "terms": indicator.get("terms", []) or [],
        "reference": indicator.get("reference", "") or "",
        "reference_url": indicator.get("reference_url", "") or "",
        "status": "published",
    }


def build_theme_lookup(source: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for theme_key, theme in source.get("KSI", {}).items():
        theme_code = theme.get("id") or theme_key
        for ind_code in theme.get("indicators", {}):
            mapping[ind_code] = theme_code
    return mapping


def diff_catalog(
    source: dict[str, Any], prior: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    new_themes: dict[str, dict[str, Any]] = {}
    new_indicators: dict[str, dict[str, Any]] = {}
    for theme_key, theme in source.get("KSI", {}).items():
        theme_code = theme.get("id") or theme_key
        new_themes[theme_code] = derive_theme_state(theme)
        for ind_code, indicator in theme.get("indicators", {}).items():
            new_indicators[ind_code] = derive_indicator_state(ind_code, indicator)

    pt = prior["themes"]
    pi = prior["indicators"]
    return {
        "themes_added": {k: v for k, v in new_themes.items() if k not in pt},
        "themes_modified": {
            k: v for k, v in new_themes.items() if k in pt and pt[k] != v
        },
        "themes_removed": {k: pt[k] for k in pt if k not in new_themes},
        "indicators_added": {k: v for k, v in new_indicators.items() if k not in pi},
        "indicators_modified": {
            k: v for k, v in new_indicators.items() if k in pi and pi[k] != v
        },
        "indicators_removed": {k: pi[k] for k in pi if k not in new_indicators},
        "new_indicators_count": len(new_indicators),
        "new_themes_count": len(new_themes),
    }


# Wave assembly --------------------------------------------------------------


def assemble_wave(
    *,
    diff: dict[str, Any],
    theme_lookup: dict[str, str],
    namespace: uuid.UUID,
    wave_index: int,
    wave_filename: str,
    is_initial: bool,
    source_info: dict[str, Any],
    commits: list[dict[str, Any]],
    prior_catalog_size: int,
    flag_bag: FlagBag,
) -> dict[str, Any]:
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    deprecated_count = len(diff["indicators_removed"])
    new_catalog_size = diff["new_indicators_count"]

    description_payload = {
        "schema_version": "v0",
        "source": source_info,
        "commits": commits,
        "wave": {
            "index": wave_index,
            "filename": wave_filename,
            "authored_at": now_iso,
            "authored_by": AUTHORED_BY,
            "is_initial": is_initial,
        },
        "changes": {
            "themes_added": len(diff["themes_added"]),
            "themes_modified": len(diff["themes_modified"]),
            "themes_removed": len(diff["themes_removed"]),
            "indicators_added": len(diff["indicators_added"]),
            "indicators_modified": len(diff["indicators_modified"]),
            "indicators_deprecated": deprecated_count,
            "catalog_size_before": prior_catalog_size,
            "catalog_size_after": new_catalog_size,
            "deletion_ratio": (
                deprecated_count / prior_catalog_size if prior_catalog_size > 0 else 0.0
            ),
        },
        "safety": {
            "review_required": flag_bag.has_warn or flag_bag.has_block,
            "flags": flag_bag.as_list(),
        },
    }

    jsonschema.validate(description_payload, load_wave_schema())

    wave_batch_id = ns_uuid(
        namespace, "wave", f"{source_info['commit_to']}:{wave_filename}"
    )

    def theme_node(code: str, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "entity": {
                "entity_id": ns_uuid(namespace, "ksi_theme", code),
                "entity_type": "ksi_theme",
                "name": state.get("name") or code,
                "dimensions": {"compliance": "fedramp-20x"},
            },
            "node": state,
        }

    def indicator_node(code: str, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "entity": {
                "entity_id": ns_uuid(namespace, "ksi_indicator", code),
                "entity_type": "ksi_indicator",
                "name": state.get("name") or code,
                "dimensions": {"compliance": "fedramp-20x"},
            },
            "node": state,
        }

    nodes: list[dict[str, Any]] = []
    for code, state in sorted(diff["themes_added"].items()):
        nodes.append(theme_node(code, state))
    for code, state in sorted(diff["themes_modified"].items()):
        nodes.append(theme_node(code, state))
    for code, state in sorted(diff["indicators_added"].items()):
        nodes.append(indicator_node(code, state))
    for code, state in sorted(diff["indicators_modified"].items()):
        nodes.append(indicator_node(code, state))
    for code, state in sorted(diff["indicators_removed"].items()):
        deprecated_state = dict(state)
        deprecated_state["status"] = "deprecated"
        nodes.append(indicator_node(code, deprecated_state))

    # Edges: one CONTAINS_INDICATOR per newly-added indicator (deterministic id).
    edges: list[dict[str, Any]] = []
    for ind_code in sorted(diff["indicators_added"]):
        theme_code = theme_lookup.get(ind_code)
        if not theme_code:
            continue
        edges.append(
            {
                "entity": {
                    "entity_id": ns_uuid(
                        namespace,
                        "edge:CONTAINS_INDICATOR",
                        f"{theme_code}->{ind_code}",
                    ),
                    "entity_type": "edge",
                    "dimensions": {"compliance": "fedramp-20x"},
                },
                "edge": {
                    "from_entity_id": ns_uuid(namespace, "ksi_theme", theme_code),
                    "to_entity_id": ns_uuid(namespace, "ksi_indicator", ind_code),
                    "edge_type": "CONTAINS_INDICATOR",
                    "properties": {},
                },
            }
        )

    batch = {
        "batch_entity": {
            "entity_id": wave_batch_id,
            "entity_type": "batch",
            "name": f"FedRAMP 20x KSI wave {wave_index} ({source_info['commit_to'][:7]})",
            "dimensions": {},
        },
        "batch_node": {
            "source": "plugins.fedramp_20x_ksi.skills.refresh-ksi-catalog",
            "name": f"FedRAMP 20x KSI wave {wave_index} ({source_info['commit_to'][:7]})",
            "description": f"Wave integrating upstream commit {source_info['commit_to']}.",
            "description_json": {"format": WAVE_FORMAT, "data": description_payload},
        },
        "nodes": nodes,
        "edges": edges,
    }

    return {"metadata": {"grift_version": "0"}, "_reserved": {}, "batches": [batch]}


# Main ------------------------------------------------------------------------


def run(dry_run: bool, output_format: str) -> int:
    bag = FlagBag()
    origin = load_source_origin()
    safety = load_safety_config()
    namespace = load_uuid_namespace()
    state = load_state_manifest()

    result: dict[str, Any] = {
        "tool": "refresh-ksi-catalog",
        "tool_version": "v0",
        "started_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }

    # Integrity
    check_origin(origin, bag)
    try:
        current_sha = upstream_head_sha()
    except RuntimeError as exc:
        bag.add("block", "SOURCE_MISSING", f"Could not read upstream HEAD: {exc}")
        return _finalize(bag, result, None, None, output_format)

    prior_sha = state.get("last_integrated_sha")
    result["source_commit"] = current_sha
    result["prior_commit"] = prior_sha

    if prior_sha == current_sha:
        bag.add("info", "REFRESH_OK", "Upstream HEAD unchanged; no refresh needed")
        result["no_op"] = True
        return _finalize(bag, result, None, None, output_format)

    check_history_integrity(prior_sha, current_sha, bag)
    if bag.has_block:
        return _finalize(bag, result, None, None, output_format)

    # Source files
    src_bytes, schema_bytes = check_source_files(bag)
    if bag.has_block or src_bytes is None or schema_bytes is None:
        return _finalize(bag, result, None, None, output_format)
    check_schema_drift(schema_bytes, bag)
    if bag.has_block:
        return _finalize(bag, result, None, None, output_format)

    try:
        source = json.loads(src_bytes)
    except json.JSONDecodeError as exc:
        bag.add("block", "SCHEMA_VALIDATION", f"Source JSON parse error: {exc}")
        return _finalize(bag, result, None, None, output_format)

    validate_against_pinned_schema(source, bag)
    if bag.has_block:
        return _finalize(bag, result, None, None, output_format)

    check_structural_caps(source, bag)
    check_character_classes(source, bag)
    if bag.has_block:
        return _finalize(bag, result, None, None, output_format)

    check_code_formats(source, bag)
    run_denylist_on_ksi(source, safety, bag)
    if bag.has_block:
        return _finalize(bag, result, None, None, output_format)

    # Commit metadata
    commits = upstream_commits_between(prior_sha, current_sha)
    check_commits(commits, origin, safety, bag)

    # Diff and deletion-ratio guard
    prior_state = reconstruct_prior_state()
    prior_catalog_size = len(prior_state["indicators"])
    diff = diff_catalog(source, prior_state)
    deprecated_count = len(diff["indicators_removed"])
    deletion_ratio = (
        deprecated_count / prior_catalog_size if prior_catalog_size > 0 else 0.0
    )
    if deletion_ratio > MASS_DELETION_RATIO:
        bag.add(
            "block",
            "MASS_DELETION",
            f"Deletion ratio {deletion_ratio:.2%} exceeds {MASS_DELETION_RATIO:.0%} threshold "
            f"({deprecated_count}/{prior_catalog_size} indicators)",
        )
        return _finalize(bag, result, None, None, output_format)

    # Deletion warn (always fires when anything is dropped, unless mass-deletion already blocked)
    for code in diff["indicators_removed"]:
        bag.add("warn", "INDICATOR_DELETED", f"{code} dropped from source")
    for code in diff["themes_removed"]:
        bag.add("warn", "THEME_DELETED", f"{code} dropped from source")

    # Churn
    churn_count = (
        len(diff["indicators_added"])
        + len(diff["indicators_modified"])
        + deprecated_count
    )
    if prior_catalog_size > 0 and churn_count / prior_catalog_size > 0.5:
        bag.add(
            "warn",
            "CHURN_HIGH",
            f"Churn {churn_count}/{prior_catalog_size} > 50% in one wave",
        )

    # Wave assembly
    rules_version = source.get("info", {}).get("version", "")
    rules_last_updated = source.get("info", {}).get("last_updated", "")
    commit_to_date = commits[0]["date"] if commits else ""
    commit_from_date = None
    is_initial = prior_sha is None
    wave_index = len(state.get("waves", [])) + 1
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    prefix = "ksi-initial" if is_initial else "ksi-wave"
    wave_filename = f"{prefix}-{today}.grift.json"

    source_info = {
        "repo": origin["expected_url"],
        "file": origin["source_json_path"],
        "file_sha256": hashlib.sha256(src_bytes).hexdigest(),
        "rules_version": rules_version,
        "rules_last_updated": rules_last_updated,
        "commit_from": prior_sha,
        "commit_to": current_sha,
        "commit_from_date": commit_from_date,
        "commit_to_date": commit_to_date,
    }

    if is_initial:
        bag.add(
            "info", "INITIAL_WAVE", "No prior baseline; full catalog emitted as new"
        )

    theme_lookup = build_theme_lookup(source)
    wave_doc = assemble_wave(
        diff=diff,
        theme_lookup=theme_lookup,
        namespace=namespace,
        wave_index=wave_index,
        wave_filename=wave_filename,
        is_initial=is_initial,
        source_info=source_info,
        commits=commits,
        prior_catalog_size=prior_catalog_size,
        flag_bag=bag,
    )

    # Write wave and update state manifest
    wave_path_rel = f"grift/{wave_filename}"
    wave_path = PLUGIN_ROOT / wave_path_rel
    if not dry_run:
        GRIFT_DIR.mkdir(parents=True, exist_ok=True)
        wave_path.write_text(json.dumps(wave_doc, indent=2) + "\n")
        state["last_integrated_sha"] = current_sha
        state["last_integrated_date"] = commit_to_date
        state["last_integrated_file_sha256"] = source_info["file_sha256"]
        state.setdefault("waves", []).append(
            {
                "index": wave_index,
                "filename": wave_path_rel,
                "sha": current_sha,
                "authored_at": datetime.now(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
            }
        )
        save_state_manifest(state)

    result["wave_filename"] = wave_path_rel
    result["wave_is_initial"] = is_initial
    result["themes_added"] = len(diff["themes_added"])
    result["indicators_added"] = len(diff["indicators_added"])
    result["indicators_modified"] = len(diff["indicators_modified"])
    result["indicators_deprecated"] = deprecated_count
    result["catalog_size_after"] = diff["new_indicators_count"]

    if not bag.has_warn and not bag.has_block:
        bag.add("info", "REFRESH_OK", "No anomalies detected")

    return _finalize(bag, result, wave_doc, wave_path_rel, output_format)


def _finalize(
    bag: FlagBag,
    result: dict[str, Any],
    wave_doc: dict[str, Any] | None,
    wave_path: str | None,
    output_format: str,
) -> int:
    result["flags"] = bag.as_list()
    result["blocked"] = bag.has_block
    result["review_required"] = bag.has_warn or bag.has_block
    result["finished_at"] = (
        datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )

    if output_format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(
            f"refresh-ksi-catalog: blocked={bag.has_block} review_required={result['review_required']}"
        )
        for f in bag.flags:
            print(f"  [{f.severity}] {f.code}: {f.detail}")
        if wave_path:
            print(f"  wave: {wave_path}")

    return 1 if bag.has_block else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refresh FedRAMP 20x KSI catalog from upstream submodule"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write wave file or update state manifest",
    )
    parser.add_argument(
        "--output-format",
        choices=("json", "text"),
        default="text",
        help="stdout format",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Alias for --output-format json (reserved for CI-specific defaults)",
    )
    args = parser.parse_args(argv)
    if args.ci:
        args.output_format = "json"
    return run(dry_run=args.dry_run, output_format=args.output_format)


if __name__ == "__main__":
    sys.exit(main())
