---
disable-model-invocation: true
description: ARS academic-paper `disclosure` mode — venue applicability/status bundle or policy-anchor render
---

First invoke the Skill tool with `skill: "ars:academic-paper"`. Pass the mode and the user's request described below as its arguments. Use the loaded skill and its supporting files before producing the result.

Trigger the `academic-paper` skill in standalone `disclosure` mode. Agent 9 must load `${CODEBUDDY_PLUGIN_ROOT}/skills/academic-paper/references/disclosure_mode_protocol.md` before rendering; the generic formatter disclosure is not a fallback. The default venue path returns `REQUIRED`, `ACTION_ONLY`, `NOT_REQUIRED`, or `UNKNOWN` applicability plus an explicit typed halt status when needed (15 policy targets supported: ICLR / NeurIPS / Nature / Science / ACL / EMNLP plus medical-publishing targets — ICMJE / NEJM / The Lancet / JAMA / BMJ / PLOS / Frontiers / publisher-wide 中华护理杂志社 / journal-level 国际眼科杂志). The `--policy-anchor` path uses its separate anchor-specific renderer. Fidelity spectrum, low oversight.

Mode reference: `${CODEBUDDY_PLUGIN_ROOT}/MODE_REGISTRY.md` § academic-paper.
Skill entry: `${CODEBUDDY_PLUGIN_ROOT}/skills/academic-paper/SKILL.md`.

Resolve plugin resources from `${CODEBUDDY_PLUGIN_ROOT}`, not from the paper project's working directory. If the skill or a required file cannot be loaded, report the loading failure and stop; do not substitute this command summary for the mode instructions.
