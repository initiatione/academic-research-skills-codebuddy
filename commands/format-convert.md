---
disable-model-invocation: true
description: ARS academic-paper `format-convert` mode — convert to LaTeX / DOCX / PDF / Markdown
---

First invoke the Skill tool with `skill: "ars:academic-paper"`. Pass the mode and the user's request described below as its arguments. Use the loaded skill and its supporting files before producing the result.

Trigger the `academic-paper` skill in `format-convert` mode. Converts a paper between LaTeX, DOCX (via Pandoc), PDF, or Markdown, and converts citation styles between major formats. Fidelity spectrum, low oversight.

Mode reference: `${CODEBUDDY_PLUGIN_ROOT}/MODE_REGISTRY.md` § academic-paper.
Skill entry: `${CODEBUDDY_PLUGIN_ROOT}/skills/academic-paper/SKILL.md`.

Resolve plugin resources from `${CODEBUDDY_PLUGIN_ROOT}`, not from the paper project's working directory. If the skill or a required file cannot be loaded, report the loading failure and stop; do not substitute this command summary for the mode instructions.
