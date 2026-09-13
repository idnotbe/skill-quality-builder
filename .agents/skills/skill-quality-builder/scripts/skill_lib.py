#!/usr/bin/env python3
"""Conservative, dependency-free utilities for local Agent Skill bundles.

This is NOT a general YAML parser or a sandbox. Inspect a stable trusted snapshot;
concurrent hostile filesystem mutation is outside the threat model.
"""
from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

MAX_FILES = 2000
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv", "node_modules"}
SKIP_SUFFIXES = {".pyc", ".pyo"}
SENSITIVE_FILENAMES = {
    ".git-credentials",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "auth.json",
    "client-secret.json",
    "credentials.json",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "secret.json",
    "secrets.json",
    "service-account.json",
    "token",
    "token.txt",
}
SENSITIVE_SUFFIXES = {".jks", ".key", ".keystore", ".p12", ".pem", ".pfx"}
SENSITIVE_PATH_SUFFIXES = {
    (".config", "gh", "hosts.yml"),
    (".docker", "config.json"),
    (".kube", "config"),
}
NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
CORE_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
INLINE_LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^\s)]+)(?:\s+[\"'][^\n]*?[\"'])?\s*\)")


class SkillError(ValueError):
    """Expected input or filesystem-policy error."""


def validate_name(name: str) -> None:
    """Enforce this tool's portable ASCII naming profile."""
    if not isinstance(name, str) or not 1 <= len(name) <= 64 or not NAME_RE.fullmatch(name):
        raise SkillError("Name must be 1–64 ASCII lowercase letters/digits, with single internal hyphens.")


def issue(level: str, code: str, message: str, path: str = "", line: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"level": level, "code": code, "message": message}
    if path:
        out["path"] = path
    if line is not None:
        out["line"] = line
    return out


def inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def is_link_like(entry_stat: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attributes = getattr(entry_stat, "st_file_attributes", 0)
    return stat.S_ISLNK(entry_stat.st_mode) or bool(attributes & reparse_flag)


def inventory(root: Path) -> tuple[list[Path], list[dict[str, Any]], list[str]]:
    """Never follow symlinks. Reject special files; bound traversal and total size."""
    issues: list[dict[str, Any]] = []
    excluded: list[str] = []
    files: list[Path] = []
    try:
        root_stat = root.lstat()
    except FileNotFoundError:
        return [], [issue("error", "not_directory", "Skill directory does not exist.", str(root))], []
    except OSError as exc:
        return [], [issue("error", "read_directory", str(exc), str(root))], []
    if is_link_like(root_stat):
        return [], [issue("error", "symlink", "The skill root must not be a symlink or Windows reparse point.", str(root))], []
    if not stat.S_ISDIR(root_stat.st_mode):
        return [], [issue("error", "not_directory", "Skill directory does not exist.", str(root))], []
    total = 0
    entries_seen = 0
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            children = sorted(directory.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            issues.append(issue("error", "read_directory", str(exc), str(directory)))
            continue
        for p in children:
            rel = p.relative_to(root).as_posix()
            entries_seen += 1
            if entries_seen > MAX_FILES * 4:
                issues.append(issue("error", "entry_limit", "Too many filesystem entries to inspect safely."))
                return files, issues, excluded
            try:
                entry_stat = p.lstat()
                mode = entry_stat.st_mode
                if is_link_like(entry_stat):
                    issues.append(issue("error", "symlink", "Symlinks and Windows reparse points are rejected by this packaging profile.", rel))
                elif stat.S_ISDIR(mode):
                    if p.name.casefold() in SKIP_DIRS:
                        excluded.append(rel + "/")
                    else:
                        stack.append(p)
                elif stat.S_ISREG(mode):
                    if p.suffix.lower() in SKIP_SUFFIXES:
                        excluded.append(rel)
                        continue
                    size = p.stat().st_size
                    total += size
                    files.append(p)
                    if size > MAX_FILE_BYTES:
                        issues.append(issue("error", "file_size_limit", f"File exceeds {MAX_FILE_BYTES} bytes.", rel))
                    if total > MAX_TOTAL_BYTES:
                        issues.append(issue("error", "total_size_limit", f"Bundle exceeds {MAX_TOTAL_BYTES} bytes."))
                        return files, issues, excluded
                    if len(files) > MAX_FILES:
                        issues.append(issue("error", "file_count_limit", f"Bundle exceeds {MAX_FILES} files."))
                        return files, issues, excluded
                else:
                    issues.append(issue("error", "special_file", "Non-regular filesystem entry rejected.", rel))
            except OSError as exc:
                issues.append(issue("error", "read_entry", str(exc), rel))
    return sorted(files), issues, sorted(excluded)


def likely_secret(path: Path) -> bool:
    name = path.name.lower()
    parts = tuple(part.lower() for part in path.parts)
    if name in {".env.example", ".env.sample", ".env.template"}:
        return False
    return (
        name == ".env"
        or name.startswith(".env.")
        or path.suffix.lower() in SENSITIVE_SUFFIXES
        or name in SENSITIVE_FILENAMES
        or any(parts[-len(suffix):] == suffix for suffix in SENSITIVE_PATH_SUFFIXES)
    )


def parse_frontmatter(text: str) -> tuple[dict[str, str | None], str, list[dict[str, Any]]]:
    """Parse ordinary string scalars only. None means present but not interpreted.

    Unsupported YAML is a warning, not a claim of validity or invalidity. Supports
    JSON-compatible double-quoted, YAML single-quoted, plain, and |/> block strings.
    Mapping metadata and product-specific values require separate host validation.
    """
    problems: list[dict[str, Any]] = []
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}, text, [issue("error", "frontmatter_missing", "SKILL.md must begin with a --- frontmatter delimiter.", "SKILL.md", 1)]
    end = next((i for i in range(1, len(lines)) if lines[i] == "---"), None)
    if end is None:
        return {}, "", [issue("error", "frontmatter_unclosed", "Closing --- delimiter missing.", "SKILL.md")]
    fields: dict[str, str | None] = {}
    i = 1
    while i < end:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):(?:\s+(.*)|\s*)$", line)
        if not match:
            problems.append(issue("warning", "yaml_unsupported", "Syntax outside the scalar profile; validate with the host's YAML parser.", "SKILL.md", i + 1))
            i += 1
            continue
        key, raw = match.group(1), (match.group(2) or "").strip()
        if key in fields:
            problems.append(issue("error", "duplicate_field", f"Duplicate frontmatter field: {key}", "SKILL.md", i + 1))
        if key not in CORE_FIELDS:
            problems.append(issue("warning", "host_field", f"Preserved host-specific/unrecognized field: {key}; not validated.", "SKILL.md", i + 1))
        value: str | None = None
        if raw in {"|", "|-", "|+", ">", ">-", ">+"}:
            block: list[str] = []
            j = i + 1
            while j < end and (not lines[j].strip() or lines[j].startswith(" ")):
                block.append(lines[j])
                j += 1
            indents = [len(x) - len(x.lstrip(" ")) for x in block if x.strip()]
            margin = min(indents) if indents else 0
            cleaned = [x[margin:] if x.strip() else "" for x in block]
            value = ("\n" if raw.startswith("|") else " ").join(cleaned).strip()
            i = j - 1
        elif raw.startswith('"'):
            try:
                decoded = json.loads(raw)
                if isinstance(decoded, str):
                    value = decoded
            except (ValueError, TypeError):
                pass
            if value is None:
                problems.append(issue("warning", "yaml_unsupported", f"Double-quoted {key} is not a supported JSON-compatible scalar; host validation required.", "SKILL.md", i + 1))
        elif raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
            inner = raw[1:-1]
            if re.search(r"(?<!')'(?!')", inner):
                problems.append(issue("warning", "yaml_unsupported", f"Quoted {key} requires manual YAML review.", "SKILL.md", i + 1))
            else:
                value = inner.replace("''", "'")
        elif not raw and i + 1 < end and lines[i + 1].startswith(" "):
            problems.append(issue("warning", "yaml_unsupported", f"Nested {key} is not validated by this scalar-only helper.", "SKILL.md", i + 1))
            j = i + 1
            while j < end and (not lines[j].strip() or lines[j].startswith(" ")):
                j += 1
            i = j - 1
        elif raw and (raw[0] in "[{&*!'" or ": " in raw or raw.lower() in {"null", "true", "false", "~"} or re.fullmatch(r"[-+]?\d+(?:\.\d+)?", raw)):
            problems.append(issue("warning", "yaml_unsupported", f"Potential non-string or advanced YAML in {key}; host validation required.", "SKILL.md", i + 1))
        else:
            value = re.split(r"\s+#", raw, maxsplit=1)[0].rstrip()
        fields[key] = value
        i += 1
    return fields, "\n".join(lines[end + 1:]), problems


def markdown_links(text: str) -> list[tuple[int, str]]:
    """Ordinary inline links only; skip fenced code and inline code spans."""
    result: list[tuple[int, str]] = []
    fence_char = ""
    fence_len = 0
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            run = marker.group(1)
            if not fence_char:
                fence_char, fence_len = run[0], len(run)
            elif run[0] == fence_char and len(run) >= fence_len:
                fence_char = ""
            continue
        if fence_char:
            continue
        without_code = re.sub(r"(`+).*?\1", "", line)
        for match in INLINE_LINK.finditer(without_code):
            result.append((number, match.group(1).strip("<>")))
    return result


def lint_skill(root: Path) -> dict[str, Any]:
    root = Path(os.path.abspath(root.expanduser()))
    files, problems, excluded = inventory(root)
    stats: dict[str, Any] = {"file_count": len(files), "limits": {"max_files": MAX_FILES, "max_file_bytes": MAX_FILE_BYTES, "max_total_bytes": MAX_TOTAL_BYTES}}
    if not root.is_dir() or root.is_symlink():
        return _report(root, stats, problems, excluded)
    skill = next((path for path in files if path.relative_to(root).as_posix() == "SKILL.md"), None)
    if skill is None:
        problems.append(issue("error", "skill_missing", "Exact, case-sensitive SKILL.md filename is required.", "SKILL.md"))
        return _report(root, stats, problems, excluded)
    if any(p["code"] in {"file_size_limit", "total_size_limit", "file_count_limit", "entry_limit"} for p in problems):
        return _report(root, stats, problems, excluded)
    try:
        text = skill.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        problems.append(issue("error", "skill_unreadable", str(exc), "SKILL.md"))
        return _report(root, stats, problems, excluded)
    fields, body, front_problems = parse_frontmatter(text)
    problems.extend(front_problems)
    for key in ("name", "description"):
        if key not in fields:
            problems.append(issue("error", "required_field", f"Missing required field: {key}", "SKILL.md"))
        elif fields[key] is None:
            problems.append(issue("error", "unparsed_required_field", f"Required field must be an ordinary string: {key}", "SKILL.md"))
        elif not fields[key].strip():
            problems.append(issue("error", "empty_field", f"Required field is empty: {key}", "SKILL.md"))
    name = fields.get("name")
    if name:
        try:
            validate_name(name)
        except SkillError as exc:
            problems.append(issue("error", "name_profile", str(exc), "SKILL.md"))
        if name != root.name:
            problems.append(issue("error", "name_directory", "Frontmatter name must match the skill directory name.", "SKILL.md"))
    for key, limit in (("description", 1024), ("compatibility", 500)):
        val = fields.get(key)
        if val is not None and len(val) > limit:
            problems.append(issue("error", "field_length", f"{key} exceeds {limit} characters.", "SKILL.md"))
    if "compatibility" in fields and fields["compatibility"] is not None and not fields["compatibility"].strip():
        problems.append(issue("error", "empty_compatibility", "compatibility must be nonempty when provided.", "SKILL.md"))
    stats.update({"skill_lines": len(text.splitlines()), "skill_characters": len(text), "skill_bytes": len(text.encode("utf-8")), "description_characters": len(fields.get("description") or "")})
    if stats["skill_lines"] > 500:
        problems.append(issue("warning", "root_length", "Root exceeds the 500-line soft guideline; consider conditional references.", "SKILL.md"))
    if not body.strip():
        problems.append(issue("warning", "empty_body", "No execution instructions are present.", "SKILL.md"))
    if re.search(r"\b(?:TODO|TBD)\b|\[DRAFT\]|<FILL", body):
        problems.append(issue("warning", "scaffold", "Unfinished scaffolding detected; complete before release.", "SKILL.md"))
    if not markdown_links(body) and any(p.relative_to(root).parts[0] == "references" for p in files):
        problems.append(issue("warning", "undiscoverable_references", "References exist but no ordinary inline links occur in SKILL.md.", "SKILL.md"))
    available = {p.resolve() for p in files}
    for p in files:
        rel = p.relative_to(root).as_posix()
        if likely_secret(p):
            problems.append(issue("error", "likely_secret", "Likely credential/private-key file; remove it from the distributable snapshot.", rel))
        if p.suffix.lower() != ".md":
            continue
        try:
            doc = p.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            problems.append(issue("error", "markdown_unreadable", str(exc), rel))
            continue
        for number, link in markdown_links(doc):
            try:
                parsed = urlsplit(link)
            except ValueError as exc:
                problems.append(issue("warning", "link_syntax", f"Link syntax requires manual review: {exc}", rel, number))
                continue
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target_text = unquote(parsed.path)
            if "\x00" in target_text or "\\" in target_text:
                problems.append(issue("warning", "path_profile", "Use ordinary forward-slash local paths; this link was not resolved.", rel, number))
                continue
            try:
                target = (p.parent / target_text).resolve()
            except (OSError, ValueError, RuntimeError) as exc:
                problems.append(issue("error", "link_resolution", str(exc), rel, number))
                continue
            if not inside(target, root.resolve()):
                problems.append(issue("error", "link_escape", f"Local reference leaves skill root: {link}", rel, number))
            elif not target.exists():
                problems.append(issue("error", "link_missing", f"Local reference does not exist: {link}", rel, number))
            elif target.is_dir() and not any(inside(item, target) for item in available):
                problems.append(issue("error", "link_unshipped_directory", f"Directory has no included files and will not exist in the archive: {link}", rel, number))
            elif target.is_file() and target not in available:
                problems.append(issue("error", "link_excluded", f"Reference points to an excluded or rejected file: {link}", rel, number))
    return _report(root, stats, problems, excluded)


def _report(root: Path, stats: dict[str, Any], problems: list[dict[str, Any]], excluded: list[str]) -> dict[str, Any]:
    errors = sum(p["level"] == "error" for p in problems)
    warnings = sum(p["level"] == "warning" for p in problems)
    return {"schema_version": 1, "tool": "skill-quality-builder-lint", "root": str(root), "status": "fail" if errors else "pass_with_warnings" if warnings else "pass", "errors": errors, "warnings": warnings, "stats": stats, "issues": problems, "excluded": excluded, "limitations": "Limited scalar YAML and ordinary inline Markdown links only. No model, semantic, complete security, host, or token-count validation."}


def init_skill(name: str, description: str, output_parent: Path) -> Path:
    validate_name(name)
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        raise SkillError("Description must contain 1–1024 characters.")
    if any(ord(c) < 32 for c in description):
        raise SkillError("Description must be a single line without control characters.")
    parent = output_parent.expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / name
    target.mkdir(exist_ok=False)
    text = f'''---
name: {name}
description: {json.dumps(description, ensure_ascii=False)}
---

# {name}

[DRAFT] This is an unfinished scaffold, not a validated skill.

## Contract

TODO: Define actual inputs, output, hard constraints, permissions, and non-goals.

## Procedure

TODO: Write concrete actions, missing-input behavior, and conditional references only if needed.

## Completion

TODO: Define observable acceptance checks and record unexecuted tests as not_run.
'''
    try:
        (target / "SKILL.md").write_text(text, encoding="utf-8")
    except BaseException:
        try:
            (target / "SKILL.md").unlink(missing_ok=True)
            target.rmdir()
        except OSError:
            pass
        raise
    return target
