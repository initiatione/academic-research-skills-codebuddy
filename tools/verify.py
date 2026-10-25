#!/usr/bin/env python3
"""Static verification for the CodeBuddy distribution of academic-research-skills.

Checks, in order of how badly each one breaks a run:
  1. manifest      — plugin.json parses, required keys present, declared paths exist
  2. frontmatter   — every SKILL.md / agent / command has parseable YAML with the
                     fields CodeBuddy needs
  3. path_refs     — every ${CODEBUDDY_PLUGIN_ROOT}/... reference resolves on disk
  4. leftovers     — no Claude-Code-only identifiers survive
  5. size          — footprint report

Exit code is 1 if any check fails, so this is usable as a pre-publish gate.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parents[1]

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
ROOT_REF = re.compile(r"\$\{CODEBUDDY_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")

# CodeBuddy accepts these for subagent `model:`; anything else is an upstream
# Claude model id that will not resolve.
ALLOWED_MODELS = {
    "inherit", "default", "lite", "reasoning",
    "minimal", "low", "medium", "high", "xhigh", "max",
}

# Paths that are documentation prose, not runtime dependencies.
IGNORE_MISSING_PREFIXES = ("docs/design/",)

# References that appear inside illustrative examples, not real file pointers.
ILLUSTRATIVE = {"scripts/plot_fig3.py"}

# Directories whose markdown the model actually reads at runtime. `scripts/` is
# internal tooling documentation that runs with cwd=repo root — not adapted.
CONTENT_DIRS = ("skills", "agents", "commands", "shared")

failures: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def check_manifest() -> dict:
    path = ROOT / ".codebuddy-plugin" / "plugin.json"
    if not path.is_file():
        fail(f"missing manifest: {path.relative_to(ROOT)}")
        return {}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"manifest is not valid JSON: {exc}")
        return {}

    for key in ("name", "version", "description"):
        if not manifest.get(key):
            fail(f"manifest missing required key: {key}")

    for key in ("skills", "agents", "commands"):
        for entry in manifest.get(key, []):
            target = (ROOT / entry).resolve()
            if not target.exists():
                fail(f"manifest {key} entry does not exist: {entry}")
    return manifest


def check_frontmatter() -> None:
    skill_files = sorted((ROOT / "skills").glob("*/SKILL.md"))
    if len(skill_files) != 5:
        fail(f"expected 5 SKILL.md under skills/, found {len(skill_files)}")

    for path in skill_files:
        text = path.read_text(encoding="utf-8")
        match = FRONTMATTER.match(text)
        if not match:
            fail(f"{path.relative_to(ROOT)}: no YAML frontmatter")
            continue
        try:
            fm = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as exc:
            fail(f"{path.relative_to(ROOT)}: bad YAML ({exc})")
            continue
        for key in ("name", "description"):
            if not fm.get(key):
                fail(f"{path.relative_to(ROOT)}: frontmatter missing '{key}'")
        if fm.get("name") != path.parent.name:
            warn(
                f"{path.relative_to(ROOT)}: name '{fm.get('name')}' "
                f"differs from directory '{path.parent.name}'"
            )

    for path in sorted((ROOT / "agents").glob("*.md")):
        match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
        if not match:
            fail(f"agents/{path.name}: no YAML frontmatter")
            continue
        try:
            fm = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as exc:
            fail(f"agents/{path.name}: bad YAML ({exc})")
            continue
        for key in ("name", "description"):
            if not fm.get(key):
                fail(f"agents/{path.name}: missing '{key}'")
        model = fm.get("model")
        if model is not None and str(model) not in ALLOWED_MODELS:
            warn(
                f"agents/{path.name}: model '{model}' is not a CodeBuddy alias "
                f"({sorted(ALLOWED_MODELS)}) — will fall back to session model"
            )
        tools = fm.get("tools")
        if isinstance(tools, str) and "Task" in tools:
            warn(f"agents/{path.name}: declares Claude 'Task' tool; CodeBuddy uses 'Agent'")

    for path in sorted((ROOT / "commands").glob("*.md")):
        match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
        if not match:
            fail(f"commands/{path.name}: no YAML frontmatter")
            continue
        try:
            fm = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as exc:
            fail(f"commands/{path.name}: bad YAML ({exc})")
            continue
        if not fm.get("description"):
            fail(f"commands/{path.name}: missing 'description'")


def content_files():
    """Markdown the model reads at runtime (skills, agents, commands, shared)."""
    for name in CONTENT_DIRS:
        base = ROOT / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            if ".git" in path.parts:
                continue
            yield path


def check_path_refs() -> int:
    checked = 0
    for path in content_files():
        for raw in ROOT_REF.findall(path.read_text(encoding="utf-8")):
            ref = raw.rstrip(".,;:)")
            if ref.startswith(IGNORE_MISSING_PREFIXES):
                continue
            if "..." in ref or ref in ILLUSTRATIVE:
                continue
            target = ROOT / ref
            checked += 1
            if target.exists():
                continue
            # A missing file with an extension breaks a run; a missing bare path
            # is usually a directory the prose names loosely — warn, don't fail.
            if "." in Path(ref).name:
                fail(f"{path.relative_to(ROOT)}: dangling reference -> {ref}")
            else:
                warn(f"{path.relative_to(ROOT)}: reference not found -> {ref}")
    return checked


def check_leftovers() -> None:
    bad_tokens = [
        "CLAUDE_PLUGIN_ROOT",
        "academic-research-skills:",
        ".claude-plugin",
    ]
    for path in content_files():
        text = path.read_text(encoding="utf-8")
        for token in bad_tokens:
            if token in text:
                fail(f"{path.relative_to(ROOT)}: leftover '{token}'")

    # Bare root-relative refs in the body (frontmatter pointers are intentional).
    bare = re.compile(r"(?<![/\w{$])(shared|scripts)/[A-Za-z0-9_./-]+")
    for path in content_files():
        text = path.read_text(encoding="utf-8")
        match = FRONTMATTER.match(text)
        body = text[match.end():] if match else text
        hits = [m.group(0) for m in bare.finditer(body)]
        if hits:
            fail(f"{path.relative_to(ROOT)}: bare root-relative refs {hits[:3]}")


def report_size() -> None:
    total = 0
    print("\nfootprint")
    for name in ("skills", "agents", "commands", "shared", "scripts"):
        target = ROOT / name
        if not target.is_dir():
            continue
        size = sum(p.stat().st_size for p in target.rglob("*") if p.is_file())
        total += size
        print(f"  {name:10} {size / 1_048_576:6.1f} MB")
    for name in ("MODE_REGISTRY.md",):
        target = ROOT / name
        if target.is_file():
            total += target.stat().st_size
    print(f"  {'total':10} {total / 1_048_576:6.1f} MB")


def main() -> int:
    manifest = check_manifest()
    check_frontmatter()
    refs = check_path_refs()
    check_leftovers()

    print(f"plugin   : {manifest.get('name')} v{manifest.get('version')}")
    print(f"skills   : {len(list((ROOT / 'skills').glob('*/SKILL.md')))}")
    print(f"agents   : {len(list((ROOT / 'agents').glob('*.md')))}")
    print(f"commands : {len(list((ROOT / 'commands').glob('*.md')))}")
    print(f"root refs: {refs} checked")
    report_size()

    if warnings:
        print(f"\nwarnings ({len(warnings)})")
        for item in warnings:
            print(f"  - {item}")
    if failures:
        print(f"\nFAILURES ({len(failures)})")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
