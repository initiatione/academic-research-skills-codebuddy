#!/usr/bin/env python3
"""Rebuild the CodeBuddy distribution of academic-research-skills from an upstream clone.

Upstream (Imbad0202/academic-research-skills) ships a *Claude Code* plugin:
    .claude-plugin/plugin.json, skills/, commands/, agents/, hooks/, shared/, scripts/

CodeBuddy's plugin format is structurally the same with two differences that this
script bridges:
    1. manifest lives in `.codebuddy-plugin/plugin.json` (not `.claude-plugin/`)
    2. `${CODEBUDDY_PLUGIN_ROOT}` is preferred; `${CLAUDE_PLUGIN_ROOT}` is only a
       compatibility alias

The bigger problem is *relative* path references. Upstream SKILL.md files write
bare `shared/...` and `scripts/...` in code spans, implicitly relative to the
plugin root. A model reading `skills/academic-paper/SKILL.md` resolves those
against the skill directory and misses. This script rewrites every such code span
to an explicit `${CODEBUDDY_PLUGIN_ROOT}/...` so resolution never depends on cwd.

Usage:
    python3 tools/sync_from_upstream.py --upstream ~/.local/share/academic-research-skills

Idempotent: regenerated directories are removed first. `tools/`, `README.md`,
`NOTICE.md` and the license files are left alone.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

PLUGIN_NAME = "ars"
UPSTREAM_REPO = "https://github.com/Imbad0202/academic-research-skills"

# Port-side revision, appended to the upstream version as `<version>-cb<N>`.
# Bump it for every release that changes anything in the plugin package —
# CodeBuddy's `plugin update` compares version strings, so an unchanged version
# means "already up to date" and the fix never ships.
PORT_REVISION = 1

SKILLS = [
    "academic-paper",
    "academic-paper-reviewer",
    "academic-pipeline",
    "deep-research",
    "sr-screener",
]

# Skills whose `scripts/...` references point at the PLUGIN-level scripts/ dir.
# sr-screener ships its own scripts/ inside the skill, so its refs stay relative.
SKILLS_WITH_PLUGIN_SCRIPTS = set(SKILLS) - {"sr-screener"}

# Upstream command file -> CodeBuddy command name (registered as /ars:<name>).
COMMANDS = {
    "ars-3w.md": "three-way.md",
    "ars-abstract.md": "abstract.md",
    "ars-cache-invalidate.md": "cache-invalidate.md",
    "ars-citation-check.md": "citation-check.md",
    "ars-disclosure.md": "disclosure.md",
    "ars-format-convert.md": "format-convert.md",
    "ars-full.md": "full.md",
    "ars-lit-review.md": "lit-review.md",
    "ars-mark-read.md": "mark-read.md",
    "ars-outline.md": "outline.md",
    "ars-plan.md": "plan.md",
    "ars-rebuttal-audit.md": "rebuttal-audit.md",
    "ars-reviewer.md": "reviewer.md",
    "ars-revision-coach.md": "revision-coach.md",
    "ars-revision.md": "revision.md",
    "ars-unmark-read.md": "unmark-read.md",
}

# Directories copied verbatim (no rewriting) — runtime dependencies.
COPY_TREES = ["shared", "scripts"]
COPY_FILES = ["MODE_REGISTRY.md", "THIRD_PARTY.md", "CITATION.cff"]

CODE_SPAN = re.compile(r"`([^`\n]+)`")

# Where a `scripts/...` reference resolves for skills that do not ship their own.
SCRIPTS_BASE = "${CODEBUDDY_PLUGIN_ROOT}/scripts"

# Bare (non-code-span) references in prose, e.g. "Use Schema 6 from shared/x.md".
# The lookbehind skips anything already prefixed ("${CODEBUDDY_PLUGIN_ROOT}/shared/")
# and relative escapes ("../shared/", "sr-screener/shared/").
PROSE_REF = re.compile(r"(?<![/\w])(shared|scripts)/([A-Za-z0-9_./-]+)")

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def rewrite_text(text: str, *, scripts_base: str) -> tuple[str, dict[str, int]]:
    """Apply all CodeBuddy adaptations to one markdown file.

    `scripts_base` is where a `scripts/...` reference should resolve to. For four
    skills that is the plugin-level scripts/ dir; sr-screener ships its own, so its
    base is `<plugin>/skills/sr-screener/scripts`.
    """
    stats = {"root_var": 0, "code_span": 0, "namespace": 0, "prose": 0}

    if "CLAUDE_PLUGIN_ROOT" in text:
        stats["root_var"] = text.count("CLAUDE_PLUGIN_ROOT")
        text = text.replace("CLAUDE_PLUGIN_ROOT", "CODEBUDDY_PLUGIN_ROOT")

    if "academic-research-skills:" in text:
        stats["namespace"] = text.count("academic-research-skills:")
        text = text.replace("academic-research-skills:", f"{PLUGIN_NAME}:")

    def absolute(span: str) -> str | None:
        """Map a bare root-relative reference to its absolute form, else None."""
        if span.startswith("shared/"):
            return "${CODEBUDDY_PLUGIN_ROOT}/" + span
        if span.startswith("scripts/"):
            return scripts_base + span[len("scripts"):]
        return None

    def fix_span(match: re.Match[str]) -> str:
        span = match.group(1)
        if span.startswith("${"):
            return match.group(0)  # already absolute
        resolved = absolute(span)
        if resolved is None:
            return match.group(0)
        stats["code_span"] += 1
        return "`" + resolved + "`"

    text = CODE_SPAN.sub(fix_span, text)

    # Second pass: bare prose references in the body (frontmatter is left alone —
    # it holds machine-readable pointers that tooling expects to stay repo-relative).
    fm = FRONTMATTER.match(text)
    head, body = (text[: fm.end()], text[fm.end():]) if fm else ("", text)

    def fix_prose(match: re.Match[str]) -> str:
        prefix, rest = match.group(1), match.group(2)
        resolved = absolute(f"{prefix}/{rest}")
        if resolved is None:
            return match.group(0)
        stats["prose"] += 1
        return resolved

    body = PROSE_REF.sub(fix_prose, body)

    # Upstream keeps the five skill dirs at the repo root; a CodeBuddy plugin keeps
    # them under skills/. Re-point ${...}/<skill>/ -> ${...}/skills/<skill>/.
    for skill in SKILLS:
        body = body.replace(
            f"${{CODEBUDDY_PLUGIN_ROOT}}/{skill}/",
            f"${{CODEBUDDY_PLUGIN_ROOT}}/skills/{skill}/",
        )
        head = head.replace(
            f"${{CODEBUDDY_PLUGIN_ROOT}}/{skill}/",
            f"${{CODEBUDDY_PLUGIN_ROOT}}/skills/{skill}/",
        )
    return head + body, stats


def rewrite_tree(root: Path, *, scripts_base: str) -> dict[str, int]:
    totals = {"root_var": 0, "code_span": 0, "namespace": 0, "prose": 0, "files": 0}
    for path in sorted(root.rglob("*.md")):
        original = path.read_text(encoding="utf-8")
        updated, stats = rewrite_text(original, scripts_base=scripts_base)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
        totals["files"] += 1
        for key in ("root_var", "code_span", "namespace", "prose"):
            totals[key] += stats[key]
    return totals


def strip_frontmatter_key(text: str, key: str) -> str:
    """Drop a top-level key from the YAML frontmatter block."""
    match = FRONTMATTER.match(text)
    if not match:
        return text
    block = match.group(1)
    # group(1) excludes the newline before the closing `---`, so the last key has
    # no trailing newline — make it optional or the final line never matches.
    cleaned = re.sub(rf"^{re.escape(key)}:.*\n?", "", block, flags=re.M)
    # Removing a trailing key leaves its leading newline behind; trim so the
    # frontmatter never grows a blank line before the closing `---`.
    cleaned = cleaned.rstrip("\n")
    return text[: match.start(1)] + cleaned + text[match.end(1):]


def build_plugin_manifest(upstream: Path, out: Path) -> dict:
    upstream_manifest = json.loads(
        (upstream / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    version = upstream_manifest.get("version", "0.0.0")
    return {
        "name": PLUGIN_NAME,
        # CodeBuddy's `plugin update` is version-gated: republishing an
        # identical version string is a silent no-op even when the content
        # changed. Port-side fixes therefore need PORT_REVISION bumped, or they
        # never reach anyone who already installed the plugin.
        "version": f"{version}-cb{PORT_REVISION}",
        "description": (
            "Academic research suite for CodeBuddy/WorkBuddy: paper writing, "
            "multi-perspective peer review, deep research, systematic-review "
            "screening, and an orchestrating pipeline. Port of "
            f"academic-research-skills v{version}."
        ),
        "author": {"name": "initiatione"},
        "homepage": UPSTREAM_REPO,
        "license": "CC-BY-NC-4.0",
        "keywords": [
            "academic",
            "research",
            "paper",
            "peer-review",
            "systematic-review",
            "codebuddy",
            "workbuddy",
        ],
        "category": "学术研究",
        "commands": [f"./commands/{name}" for name in sorted(COMMANDS.values())],
        "agents": [f"./agents/{p.name}" for p in sorted((out / "agents").glob("*.md"))],
        "skills": [f"./skills/{name}" for name in SKILLS],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()

    upstream: Path = args.upstream.expanduser().resolve()
    out: Path = args.out.expanduser().resolve()

    if not (upstream / ".claude-plugin" / "plugin.json").is_file():
        sys.stderr.write(f"not an upstream ARS clone: {upstream}\n")
        return 2

    # --- clean regenerated artifacts -------------------------------------------------
    for name in ["skills", "agents", "commands", ".codebuddy-plugin"] + COPY_TREES:
        target = out / name
        if target.is_dir():
            shutil.rmtree(target)
    for name in COPY_FILES:
        target = out / name
        if target.is_file():
            target.unlink()

    # --- skills ----------------------------------------------------------------------
    (out / "skills").mkdir(parents=True, exist_ok=True)
    skill_stats = {}
    for skill in SKILLS:
        src = upstream / skill
        dst = out / "skills" / skill
        shutil.copytree(src, dst)
        skill_stats[skill] = rewrite_tree(
            dst,
            scripts_base=(
                SCRIPTS_BASE
                if skill in SKILLS_WITH_PLUGIN_SCRIPTS
                else f"${{CODEBUDDY_PLUGIN_ROOT}}/skills/{skill}/scripts"
            ),
        )

    # --- agents ----------------------------------------------------------------------
    (out / "agents").mkdir(parents=True, exist_ok=True)
    agent_stats = {"files": 0, "root_var": 0, "code_span": 0, "namespace": 0, "prose": 0}
    for src in sorted((upstream / "agents").glob("*.md")):
        dst = out / "agents" / src.name
        shutil.copy2(src, dst)
        text, stats = rewrite_text(
            dst.read_text(encoding="utf-8"), scripts_base=SCRIPTS_BASE
        )
        dst.write_text(text, encoding="utf-8")
        agent_stats["files"] += 1
        for key in ("root_var", "code_span", "namespace", "prose"):
            agent_stats[key] += stats[key]

    # --- commands --------------------------------------------------------------------
    (out / "commands").mkdir(parents=True, exist_ok=True)
    cmd_stats = {"files": 0, "root_var": 0, "code_span": 0, "namespace": 0,
                 "prose": 0, "missing": [], "model_stripped": 0}
    for src_name, dst_name in COMMANDS.items():
        src = upstream / "commands" / src_name
        if not src.is_file():
            cmd_stats["missing"].append(src_name)
            continue
        dst = out / "commands" / dst_name
        text, stats = rewrite_text(
            src.read_text(encoding="utf-8"), scripts_base=SCRIPTS_BASE
        )
        # CodeBuddy derives a command's name from its filename and does not read a
        # `name:` key; upstream's `model: sonnet` has no CodeBuddy equivalent either.
        # Dropping both keeps the frontmatter honest about what actually applies.
        before = text
        for key in ("model", "name"):
            text = strip_frontmatter_key(text, key)
        if text != before:
            cmd_stats["model_stripped"] += 1
        dst.write_text(text, encoding="utf-8")
        cmd_stats["files"] += 1
        for key in ("root_var", "code_span", "namespace", "prose"):
            cmd_stats[key] += stats[key]

    # --- verbatim runtime trees ------------------------------------------------------
    for name in COPY_TREES:
        shutil.copytree(upstream / name, out / name)
    for name in COPY_FILES:
        shutil.copy2(upstream / name, out / name)

    # `shared/` is read by the model (rubrics, schemas, shared agent prompts), so its
    # own root-relative refs need the same treatment. `scripts/` is internal tooling
    # documentation that always runs with cwd=repo root — left verbatim.
    shared_stats = rewrite_tree(out / "shared", scripts_base=SCRIPTS_BASE)

    # --- manifest --------------------------------------------------------------------
    (out / ".codebuddy-plugin").mkdir(exist_ok=True)
    manifest = build_plugin_manifest(upstream, out)
    (out / ".codebuddy-plugin" / "plugin.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # --- report ----------------------------------------------------------------------
    print(f"upstream : {upstream}")
    print(f"out      : {out}")
    print(f"version  : {manifest['version']}")
    print()
    print(f"{'skill':26} {'files':>6} {'rootvar':>8} {'span':>6} {'prose':>6} {'ns':>4}")
    for skill, st in skill_stats.items():
        print(
            f"{skill:26} {st['files']:>6} {st['root_var']:>8} "
            f"{st['code_span']:>6} {st['prose']:>6} {st['namespace']:>4}"
        )
    print(f"{'agents':26} {agent_stats['files']:>6} {agent_stats['root_var']:>8} "
          f"{agent_stats['code_span']:>6} {agent_stats['prose']:>6} "
          f"{agent_stats['namespace']:>4}")
    print(f"{'commands':26} {cmd_stats['files']:>6} {cmd_stats['root_var']:>8} "
          f"{cmd_stats['code_span']:>6} {cmd_stats['prose']:>6} "
          f"{cmd_stats['namespace']:>4}")
    print(f"{'shared':26} {shared_stats['files']:>6} {shared_stats['root_var']:>8} "
          f"{shared_stats['code_span']:>6} {shared_stats['prose']:>6} "
          f"{shared_stats['namespace']:>4}")
    if cmd_stats["missing"]:
        print(f"\nWARNING missing upstream commands: {cmd_stats['missing']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
