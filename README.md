# academic-research-skills-codebuddy

把 [academic-research-skills](https://github.com/Imbad0202/academic-research-skills)（下称 ARS）移植成 **CodeBuddy / WorkBuddy 插件**。

上游是 Claude Code 插件。CodeBuddy 的插件格式与之高度相似但并非等价，这个仓库做的是**结构适配**，不是重写：技能内容、契约、rubric、脚本全部沿用上游，只改宿主相关的那一层。

- 上游版本：**v3.23.2**
- 移植版本：**3.23.2-cb1**（`<上游版本>-cb<N>`，N 是移植侧修订号）
- 许可：**CC BY-NC 4.0**（非商用），著作权归上游作者 Cheng-I Wu
- 内容：5 个技能 · 4 个子代理 · 16 个斜杠命令

---

## 为什么需要移植

上游依赖四个 Claude Code 专有机制，其中两个 CodeBuddy 没有等价物：

| 上游机制 | CodeBuddy 对应 | 处理方式 |
|---|---|---|
| `.claude-plugin/plugin.json` | `.codebuddy-plugin/plugin.json` | 改目录名 + 重写清单 |
| `${CLAUDE_PLUGIN_ROOT}` | `${CODEBUDDY_PLUGIN_ROOT}`（`CLAUDE_*` 仅为兼容别名） | 统一改为 `CODEBUDDY_*` |
| 技能目录在仓库根 | 插件要求放在 `skills/` | 移动 + 重写所有路径引用 |
| `commands/` 斜杠命令 | 支持，但注册为 `/<plugin>:<command>` | 去掉 `ars-` 前缀 → `/ars:plan`；并清掉 CodeBuddy 不认的 `model` / `name` 字段 |
| `agents/` 子代理 | 支持，格式基本一致 | 直接沿用 |
| `hooks/hooks.json` | 格式不同，且上游钩子在此环境无效 | **不移植**，见下文 |

### 关于钩子

上游有两个钩子，其中 `ars_write_scope_guard.py` 会在每次写操作前运行。**这里没有移植**，原因是它在 CodeBuddy 下必然是空转：

它只在 payload 的 `agent_type` 命中上游 manifest 里那批「单阶段子代理」时才拒绝写入。CodeBuddy 派发的子代理类型是 `general-purpose` / `Explore` 这类，永远不会命中。上游自己在代码注释里也承认：主会话内联运行时本来就不受该钩子约束，只靠 prompt 级 Phase Boundary 兜底。

所以不移植不降低防护等级，只是省掉每次写操作一次 Python 启动。`scripts/` 目录仍然完整保留，需要时可以手动接线。

---

## 安装

分两步：装插件、装 Python 依赖。**第二步不做的话，技能会在第一次调用脚本时崩**，因为上游脚本 import 了 pyyaml / jsonschema / pypdf / ruamel.yaml / defusedxml / requests。

### 第一步：装插件

```bash
codebuddy plugin add https://github.com/initiatione/academic-research-skills-codebuddy --yes
```

必须用 **`--yes`**（长选项）。帮助里写的是 `-y, --yes`，但实测 `-y` 不满足启用确认，会打印
`Enablement needs a TTY confirmation or --yes; keeping the package disabled.` —— 装上了，但是 disabled。

装完自查：

```bash
codebuddy plugin list | grep -A3 ars
```

期望看到 `Status: enabled`。万一仍是 `disabled`，补一条启用命令 —— **必须用完整 id**：

```bash
codebuddy plugin enable "ars@git-5acaac9bb89d4ca7a073bc99"
```

裸名字会报 `Marketplace undefined is not found`。`update` / `uninstall` 同理。

最后进会话执行 `/reload-plugins`。

#### 这个 `git-<hash>` 是怎么来的

市场 id = **`sha256(你输入的那个源字符串)[:24]`**。所以：

- `.../academic-research-skills-codebuddy` → `git-5acaac9bb89d4ca7a073bc99`
- `.../academic-research-skills-codebuddy.git` → `git-593864458ff78626630a3b21`

两个字符串算出两个 id，就是**两份独立安装**：技能和命令会出现两套，旧的那份还得单独卸载。
所以**始终用同一种写法**（上面给的是不带 `.git` 的形式），别这次带、下次不带。

### 更新

```bash
codebuddy plugin add https://github.com/initiatione/academic-research-skills-codebuddy --yes
```

对，就是**再跑一次安装命令**。源字符串一致 → 同一个市场 id → 不会产生重复安装，只会把内容换成最新提交。

`codebuddy plugin update` 在这条链路上是空转：它不会重新 clone 远端，只比对本地已有的目录，
所以即使远端已经更新、版本号已经变过，它仍然回一句 `Successfully updated` 而什么都没换。
别被这句话骗了。

装完 `/reload-plugins` 生效。Python 依赖装在 `~/.local/share/ars-venv`，**与插件目录无关，更新不丢**。

#### 如果 `codebuddy plugin *` 报 `EADDRINUSE 127.0.0.1:42599`

在 WorkBuddy 派生的 shell 里跑 CLI 会继承宿主进程的 `SERVER__PORT` 和
`CODEBUDDY_SERVICE_PROXY_URL`，CLI 会试图复用那个端口。清掉即可（`--port` 在子命令上不接受）：

```bash
env -u SERVER__PORT -u CODEBUDDY_SERVICE_PROXY_URL -u CODEBUDDY_MCP_CONFIG \
    codebuddy plugin list
```

普通终端里没有这个变量，不需要加。

### 第二步：装 Python 依赖

```bash
git clone https://github.com/initiatione/academic-research-skills-codebuddy
sh academic-research-skills-codebuddy/tools/install.sh
```

也可以直接对已安装的副本跑 —— venv 在固定的全局位置，跟哪份拷贝无关：

```bash
sh "$(ls -d ~/.workbuddy-ai/plugins/package-sources/git-*/versions/*/package | head -1)/tools/install.sh"
```

脚本做三件事：在 `~/.local/share/ars-venv` 建隔离 venv、按 `requirements.txt` 装包、逐个 import 验证。不会碰系统 Python。

随时查状态（在仓库目录或插件副本目录里跑）：

```bash
sh tools/install.sh --check
```

```
plugin root : /path/to/package
router      : present (bin/python3)
venv        : /home/you/.local/share/ars-venv/bin/python
deps        : ok
```

想放别处：`sh tools/install.sh --venv /opt/ars-venv`（会写 `python-path` 记录位置），或者直接 `export ARS_PYTHON=/opt/ars-venv/bin/python`。

### 为什么仓库里带一个 `bin/python3`

技能调用脚本的方式是 `python3 <插件根>/scripts/xxx.py`。`bin/` 会被 CodeBuddy **前置**到 Bash 的 `PATH`
（`PATH = [...pluginBinPaths, ...rest]`），所以这里的 `python3` 会优先命中。

但全局劫持 `python3` 是不能接受的，所以它是**窄范围路由器**，不是替换：

| 调用 | 行为 |
|---|---|
| `python3 <本插件>/*.py ...` | 用带依赖的解释器跑 |
| `python3 -c ...` / `-m ...` / `-` | 原样透传给真正的 python3 |
| `python3 别的项目的脚本` | 原样透传 |

带依赖的解释器按顺序找：`$ARS_PYTHON` → `<插件>/python-path` → `~/.local/share/ars-venv` → `<插件>/.venv` → 系统 python3（降级，会打印一行提示）。

这个文件**不含任何本机路径，随仓库提交**，所以 `plugin update` 换掉整个内容目录之后它还在。

### 开发/试用（不安装）

```bash
codebuddy --plugin-dir ~/dev/academic-research-skills-codebuddy
```

进入会话后运行 `/reload-plugins`，然后：

- `/agents` 里应该能看到 4 个子代理
- 输入 `/ars:` 应该能补全出 16 个命令

---

## 用法

### 斜杠命令

命令名去掉了上游的 `ars-` 前缀，因为 CodeBuddy 会自动加插件名前缀。

| 命令 | 作用 | 上游原名 |
|---|---|---|
| `/ars:plan` | 苏格拉底式引导，梳理论文结构 | `ars-plan` |
| `/ars:outline` | 生成大纲 | `ars-outline` |
| `/ars:full` | 端到端全流程 | `ars-full` |
| `/ars:abstract` | 摘要（含双语） | `ars-abstract` |
| `/ars:lit-review` | 文献综述 | `ars-lit-review` |
| `/ars:three-way` | WHY / HOW / WHAT 三段式文献扫描 | `ars-3w` |
| `/ars:reviewer` | 模拟审稿面板 | `ars-reviewer` |
| `/ars:revision` | 按审稿意见修订 | `ars-revision` |
| `/ars:revision-coach` | 修订路线图 | `ars-revision-coach` |
| `/ars:rebuttal-audit` | 审阅自己的回复信 | `ars-rebuttal-audit` |
| `/ars:citation-check` | 引文核查 | `ars-citation-check` |
| `/ars:format-convert` | 格式转换 | `ars-format-convert` |
| `/ars:disclosure` | AI 使用声明 | `ars-disclosure` |
| `/ars:mark-read` | 标记已读 | `ars-mark-read` |
| `/ars:unmark-read` | 取消标记 | `ars-unmark-read` |
| `/ars:cache-invalidate` | 清缓存 | `ars-cache-invalidate` |

### 不用命令也行

技能是模型自动调用的。直接说「用 academic-paper 的 outline 模式」和敲 `/ars:outline` 等效 —— 命令只是快捷方式，35 个模式的完整清单在 `MODE_REGISTRY.md`。

### 子代理

`/agents` 里会看到：

- `synthesis_agent` — 跨来源证据综合
- `research_architect_agent` — 研究方法与检索策略设计
- `report_compiler_agent` — APA 7.0 报告撰写
- `screening_reviewer_agent` — 系统综述双盲筛选

它们与上游定义一致，`model: inherit` 表示跟随会话模型。

---

## 排错

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: No module named 'yaml'`（或 jsonschema / pypdf / ruamel / defusedxml / requests） | 没跑第二步 | `sh tools/install.sh` |
| `ars: no dependency venv found — falling back to system python3` | 同上，venv 不在任何候选位置 | 同上，或 `export ARS_PYTHON=...` |
| 装完 `Status: disabled` | 用了 `-y` | 重装时用 `--yes`，或 `codebuddy plugin enable "ars@git-<24hex>"` |
| `/ars:` 命令补全不出来 | 插件没启用 / 没 reload | `plugin list` → `enable` → `/reload-plugins` |
| 技能和命令出现两套 | 装过两次且 URL 写法不同（带不带 `.git`） | `plugin list` 找到两个 id，`uninstall` 旧的那个 |
| `plugin enable ars` / `plugin update ars` 报 `Marketplace undefined is not found` | 裸名字定位不到市场 | 用 `ars@git-<24hex>` 完整 id |
| `plugin update` 说成功但内容没变 | 这条链路不重新 clone 远端 | 用 `plugin add <同一 URL> --yes` 更新 |
| `EADDRINUSE 127.0.0.1:42599` | 继承了宿主进程的 `SERVER__PORT` | `env -u SERVER__PORT -u CODEBUDDY_SERVICE_PROXY_URL -u CODEBUDDY_MCP_CONFIG codebuddy ...` |
| 更新后 `which python3` 不指向插件 `bin/` | 只有 CodeBuddy 的 Bash 工具会前置插件 `bin/`，你的普通终端不会 | 在会话里验证；或在终端显式 `PATH=<插件>/bin:$PATH` |
| Windows PowerShell 下脚本跑不起来 | `bin/python3` 是 POSIX sh 脚本，靠 Git Bash 生效 | 用 Git Bash，或设 `ARS_PYTHON` 并在技能里改用完整路径 |

自查顺序：`sh tools/install.sh --check` → `codebuddy plugin list` → 会话内 `which python3`。

---

## 结构

```
.
├── .codebuddy-plugin/plugin.json    # 清单
├── skills/                          # 5 个技能
│   ├── academic-paper/              # 写作：12 角色 / 11 模式
│   ├── academic-paper-reviewer/     # 审稿：5 席角色分离面板
│   ├── academic-pipeline/           # 编排：10 阶段
│   ├── deep-research/               # 调研：13 角色 / 8 模式
│   └── sr-screener/                 # 系统综述筛选（自带 scripts/）
├── agents/                          # 4 个子代理
├── commands/                        # 16 个斜杠命令
├── shared/                          # 契约 / schema / rubric（技能共用）
├── scripts/                         # 上游 Python 工具链
├── bin/python3                      # 解释器路由器（随包分发）
├── MODE_REGISTRY.md                 # 35 个模式的单一事实源
├── requirements.txt                 # 脚本运行时依赖
├── THIRD_PARTY.md  CITATION.cff     # 上游第三方声明与引用信息
└── tools/
    ├── install.sh                   # 一键装依赖 + 自检
    ├── sync_from_upstream.py        # 从上游重新生成
    ├── verify.py                    # 发布前静态校验
    └── compare_with_upstream.py     # 证明内容与上游一致
```

`python-path` 只在用 `--venv` 指定非默认位置时生成，已被 gitignore。

### 路径引用的处理

上游技能文件里写的是裸的 `shared/...` 和 `scripts/...`，隐含相对于**仓库根**。模型读 `skills/academic-paper/SKILL.md` 时会按技能目录解析，直接就读不到。

所以移植时把这类引用全部改成了显式的 `${CODEBUDDY_PLUGIN_ROOT}/...`。`sr-screener` 自带 `scripts/`，它的引用指向 `skills/sr-screener/scripts/`，其余四个指向插件根 `scripts/`。

---

## 同步上游

上游更新后，不用手改：

```bash
python3 tools/sync_from_upstream.py --upstream ~/path/to/academic-research-skills
python3 tools/verify.py
python3 tools/compare_with_upstream.py --upstream ~/path/to/academic-research-skills
```

`sync` 会重新生成 `skills/ agents/ commands/ shared/ scripts/` 和清单，`tools/`、`bin/`、README、NOTICE、LICENSE 不受影响。`verify` 检查清单合法性、frontmatter、以及全部 `${CODEBUDDY_PLUGIN_ROOT}/...` 引用是否真实存在（约 940 个）。`compare` 证明内容仍与上游逐字节一致。两者失败都返回非零。

依赖：`python3` + `pyyaml`（缺 PyYAML 时 `verify.py` 会自己转去用 `tools/install.sh` 建的那个 venv）。

发版还有一步人工动作：把 `tools/sync_from_upstream.py` 里的 `PORT_REVISION` 加一。版本号是
`<上游版本>-cb<N>`，重发同一个版本号不会让人察觉内容变了。

---

## 和上游一样吗

**内容层：一样。** 1016 个文件逐字节比对通过 —— 技能文本、契约、schema、rubric、
脚本、子代理提示，全部与上游一致，只差下文列出的机械适配。

可以自己验：

```bash
python3 tools/compare_with_upstream.py --upstream ~/path/to/academic-research-skills
```

它会**把同样的改写重新施加到上游文件上**，再要求结果与本仓库逐字节相等。
所以任何生成之后的手工改动都会立刻暴露，这个检查不依赖信任。

**能力层：一样。** 5 技能 / 4 子代理 / 16 命令 / 35 个模式全部在位。

### 差异清单（完整）

| 差异 | 性质 | 影响 |
|---|---|---|
| 清单目录 `.claude-plugin/` → `.codebuddy-plugin/` | 宿主强制 | 无 |
| 技能从仓库根移到 `skills/` | 宿主强制 | 无（路径已同步改写） |
| `${CLAUDE_PLUGIN_ROOT}` → `${CODEBUDDY_PLUGIN_ROOT}` | 命名习惯（前者仍兼容） | 无 |
| 裸 `shared/` `scripts/` 引用改为显式绝对路径 | **修复上游的潜在缺陷** | 正向 |
| 命令 `ars-plan` → `/ars:plan` | 宿主强制（自动加插件前缀） | 需要改口，有映射表 |
| 命令移除 `model: sonnet` / `name:` | 字段在 CodeBuddy 无效 | 命令继承会话模型 |
| 新增 `bin/python3` `tools/install.sh` | 宿主差异（托管解释器装不了包） | 正向 |
| **钩子未移植** | 有意 | 见下 |
| `docs/` `evals/` `tests/` `plugin-evals*/` `audits/` `pi/` `examples/` `.claude/` 未包含 | 非运行时 | 查设计文档请去上游 |
| `package.json` `pyproject.toml` 未包含 | 是 Pi 适配器和 dev 工具的配置 | 无 |
| `scripts/` 内 markdown 未做路径改写 | 有意 | 那些文档始终以仓库根为 cwd 运行 |

上游有少量**开发期自检脚本**（如 `check_version_consistency.py`）假定仓库根存在
`.claude/CLAUDE.md`，在本移植里跑会报文件不存在。它们不参与技能运行；本仓库的等价闸门是
`tools/verify.py`。

### 为什么钩子没移植

上游两个钩子里，`PreToolUse` 那个（`ars_write_scope_guard.py`）是写作用域守卫。
上游自己的技能文档写得很明确：

> a PreToolUse write-scope guard that applies only to Bucket A roles dispatched as
> separate subagents of their own agent type in an install that wires the hook;
> roles run inline in the main session by default, where only the prompt-level
> blocks apply

也就是说，这个守卫**只对「以自身 agent type 派发的单阶段子代理」生效**。CodeBuddy
派发子代理用的是 `general-purpose` / `Explore` 这类类型，不会命中上游 manifest 里的
角色名 —— 接上去也是空转，还让每次写操作多一次 Python 启动。

`SessionStart` 那个是会话启动横幅 + 每日一次版本检查，纯提示，不影响任何能力。

**所以不移植不降低防护等级** —— 失去的恰好是上游自己声明为「默认不适用」的那部分。
想强行接线的话：把上游 `hooks/` 拷进插件根，把 `hooks.json` 里的
`${CLAUDE_PLUGIN_ROOT}` 换成 `${CODEBUDDY_PLUGIN_ROOT}` 即可，格式是兼容的。

---

## 许可

内容与代码来自上游，遵循 **CC BY-NC 4.0**，禁止商业使用。详见 `LICENSE` 与 `NOTICE.md`。

本仓库仅做宿主适配，不主张对上游内容的著作权。
