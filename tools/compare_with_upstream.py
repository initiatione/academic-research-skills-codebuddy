#!/usr/bin/env python3
"""Prove (or disprove) that this port is content-identical to upstream.

The claim under test is narrow and falsifiable:

    every file differs from upstream ONLY by the mechanical adaptations in
    tools/sync_from_upstream.py — nothing was rewritten, softened, or dropped.

The method avoids trusting that claim: it re-applies the same transformation to
the upstream file and requires the result to match the port byte for byte. Any
hand edit made after generation shows up immediately as a mismatch.

Usage:
    python3 tools/compare_with_upstream.py --upstream ~/path/to/upstream
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sync_from_upstream as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def scripts_base_for(skill: str) -> str:
    if skill in S.SKILLS_WITH_PLUGIN_SCRIPTS:
        return S.SCRIPTS_BASE
    return f"${{CODEBUDDY_PLUGIN_ROOT}}/skills/{skill}/scripts"


def compare_md(upstream_file: Path, port_file: Path, scripts_base: str) -> str | None:
    """None if identical-after-adaptation, else a short reason."""
    expected, _ = S.rewrite_text(
        upstream_file.read_text(encoding="utf-8"), scripts_base=scripts_base
    )
    actual = port_file.read_text(encoding="utf-8")
    if expected == actual:
        return None
    exp_lines, act_lines = expected.splitlines(), actual.splitlines()
    for i, (a, b) in enumerate(zip(exp_lines, act_lines), 1):
        if a != b:
            return f"line {i} differs:\n      upstream→ {a[:100]}\n      port    → {b[:100]}"
    return f"line count {len(exp_lines)} vs {len(act_lines)}"


def compare_tree(
    upstream: Path, port: Path, scripts_base: str, *, verbatim: bool = False
) -> tuple[int, list[str]]:
    checked, problems = 0, []
    for src in sorted(upstream.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(upstream)
        dst = port / rel
        if not dst.is_file():
            problems.append(f"missing in port: {rel}")
            continue
        checked += 1
        if verbatim:
            # scripts/ markdown is internal tooling documentation: copied untouched,
            # because it always runs with cwd at the repo root.
            if src.read_bytes() != dst.read_bytes():
                problems.append(f"{rel}: differs from upstream (expected verbatim)")
        elif src.suffix == ".md":
            reason = compare_md(src, dst, scripts_base)
            if reason:
                problems.append(f"{rel}: {reason}")
        elif src.read_bytes() != dst.read_bytes():
            problems.append(f"{rel}: binary/text differs (copied verbatim upstream)")
    return checked, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, type=Path)
    args = parser.parse_args()
    upstream = args.upstream.expanduser().resolve()

    total, all_problems = 0, []

    for skill in S.SKILLS:
        checked, problems = compare_tree(
            upstream / skill, ROOT / "skills" / skill, scripts_base_for(skill)
        )
        total += checked
        print(f"{skill:26} {checked:4} files  {'OK' if not problems else f'{len(problems)} DIFF'}")
        all_problems += [f"skills/{skill}/{p}" for p in problems]

    checked, problems = compare_tree(upstream / "agents", ROOT / "agents", S.SCRIPTS_BASE)
    total += checked
    print(f"{'agents':26} {checked:4} files  {'OK' if not problems else f'{len(problems)} DIFF'}")
    all_problems += [f"agents/{p}" for p in problems]

    checked, problems = compare_tree(upstream / "shared", ROOT / "shared", S.SCRIPTS_BASE)
    total += checked
    print(f"{'shared':26} {checked:4} files  {'OK' if not problems else f'{len(problems)} DIFF'}")
    all_problems += [f"shared/{p}" for p in problems]

    checked, problems = compare_tree(
        upstream / "scripts", ROOT / "scripts", S.SCRIPTS_BASE, verbatim=True
    )
    total += checked
    print(f"{'scripts':26} {checked:4} files  {'OK' if not problems else f'{len(problems)} DIFF'}")
    all_problems += [f"scripts/{p}" for p in problems]

    # Commands are renamed, so pair them through the mapping table.
    cmd_checked, cmd_problems = 0, []
    for src_name, dst_name in S.COMMANDS.items():
        src = upstream / "commands" / src_name
        dst = ROOT / "commands" / dst_name
        if not src.is_file():
            cmd_problems.append(f"missing upstream: {src_name}")
            continue
        if not dst.is_file():
            cmd_problems.append(f"missing in port: {dst_name}")
            continue
        cmd_checked += 1
        expected, _ = S.rewrite_text(
            src.read_text(encoding="utf-8"), scripts_base=S.SCRIPTS_BASE
        )
        expected = S.strip_frontmatter_key(expected, "model")
        expected = S.strip_frontmatter_key(expected, "name")
        if expected != dst.read_text(encoding="utf-8"):
            cmd_problems.append(f"{src_name} -> {dst_name}: differs")
    total += cmd_checked
    print(f"{'commands':26} {cmd_checked:4} files  "
          f"{'OK' if not cmd_problems else f'{len(cmd_problems)} DIFF'}")
    all_problems += [f"commands/{p}" for p in cmd_problems]

    print(f"\n{total} files compared")
    if all_problems:
        print(f"\nMISMATCHES ({len(all_problems)})")
        for item in all_problems[:20]:
            print(f"  - {item}")
        return 1
    print("content identical to upstream, modulo the documented adaptations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
