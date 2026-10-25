# NOTICE

## 上游

本仓库是 [academic-research-skills](https://github.com/Imbad0202/academic-research-skills) 的
**宿主适配版本**（CodeBuddy / WorkBuddy）。

- 原作者：**Cheng-I Wu (Imbad0202)**
- 上游版本：**v3.23.2**
- 上游许可：Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
- 著作权：Copyright (c) 2026 Cheng-I Wu

`skills/`、`agents/`、`commands/`、`shared/`、`scripts/`、`MODE_REGISTRY.md`
的内容均派生自上游，本仓库不主张其著作权。

## 本仓库所做的修改

仅为在 CodeBuddy / WorkBuddy 上运行而做的结构性适配，**未改动任何技能的方法论内容**：

1. 清单目录 `.claude-plugin/` → `.codebuddy-plugin/`
2. 路径变量 `CLAUDE_PLUGIN_ROOT` → `CODEBUDDY_PLUGIN_ROOT`
3. 技能目录移入 `skills/`，并把裸的 `shared/`、`scripts/` 引用改写为
   `${CODEBUDDY_PLUGIN_ROOT}/...` 显式路径
4. 插件命名空间 `academic-research-skills:` → `ars:`
5. 命令文件去掉 `ars-` 前缀（`/ars-plan` → `/ars:plan`）
6. **未包含** 上游的 `hooks/`、`docs/`、`evals/`、`tests/`、`plugin-evals/`

修改清单与理由见 `README.md`。

## 许可继承

上游为 CC BY-NC 4.0（署名—非商业性使用）。派生作品继承同一许可：
**允许非商业使用与修改，必须署名上游作者，不得用于商业目的。**

若需商业使用，请联系上游作者取得授权。
