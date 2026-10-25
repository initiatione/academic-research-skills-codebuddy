---
disable-model-invocation: true
description: ARS academic-paper `outline-only` mode — detailed outline + evidence map
---

First invoke the Skill tool with `skill: "ars:academic-paper"`. Pass the mode and the user's request described below as its arguments. Use the loaded skill and its supporting files before producing the result.

Trigger the `academic-paper` skill in `outline-only` mode. Produces a detailed paper outline with evidence map, no full draft. Balanced spectrum, high oversight.

Mode reference: `${CODEBUDDY_PLUGIN_ROOT}/MODE_REGISTRY.md` § academic-paper.
Skill entry: `${CODEBUDDY_PLUGIN_ROOT}/skills/academic-paper/SKILL.md`.

Resolve plugin resources from `${CODEBUDDY_PLUGIN_ROOT}`, not from the paper project's working directory. If the skill or a required file cannot be loaded, report the loading failure and stop; do not substitute this command summary for the mode instructions.
