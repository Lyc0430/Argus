<div align="center">

<img src="docs/assets/argus-mascot.svg" width="140" alt="Argus 多眼哨兵 Agent 吉祥物">

# Argus

### 面向科研与工程的持久、可审查自主运行时

让长期 Agent 能够规划、执行、验证、暂停，并在一次模型调用之后继续推进。

**当前为 Preview v0.1.1 · 正式开源版正在路上。**

[![GitHub Stars](https://img.shields.io/github/stars/lbx154/Argus?style=flat-square)](https://github.com/lbx154/Argus/stargazers)
[![License](https://img.shields.io/github/license/lbx154/Argus?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![arXiv](https://img.shields.io/badge/arXiv-2608.05144-b31b1b?style=flat-square&logo=arxiv&logoColor=white)](https://arxiv.org/abs/2608.05144)

[官方网站](https://argusbot.cn) · [视频演示](https://www.youtube.com/watch?v=i8Qy9HCboQE) · [技术报告 · arXiv:2608.05144](https://arxiv.org/pdf/2608.05144) · [微信群](#微信群) · [English](README.md) / **简体中文**

`Manager` → `Planner` → `Engineer` ⇄ `Reviewer`

</div>

---

## Argus 是什么？

大多数 Agent 面向一次对话或一次编码回合设计。Argus 面向真正需要持续推进的工作：保存状态、分离执行与判断，并从已经验证的进展继续，而不是每次重新开始。

| 核心能力 | 含义 |
|---|---|
| **持久状态** | 任务、检查点、决策、Skill 与证据可跨 Session 和运行时升级保存。 |
| **独立审查** | 执行与验证相互分离；正常回合由 Reviewer 给出独立判断。 |
| **四角色运行时** | Manager、Planner、Engineer 和 Reviewer 分别拥有明确的权威与职责。 |
| **真实工具调用** | Agent 直接使用文件、终端、实验、API 和可检查的产物。 |
| **领域扩展** | Vertical 可以定义专属阶段、工具、证据要求与完成标准。 |
| **多种 Backend** | 支持 GitHub Copilot CLI、Pi、Codex CLI、Claude Code 与 OpenCode。 |

## 运行模型

| | 权威 | 职责 |
|---:|---|---|
| `01` | **Manager · 控制** | 理解 operator 意图、选择工作流，并独占阶段迁移权。 |
| `02` | **Planner · 方向** | 选择下一项高价值任务，并定义它必须产出的证据。 |
| `03` | **Engineer · 执行** | 实现代码、开展调研、运行实验，并生成可检查的产物。 |
| `04` | **Reviewer · 验证** | 独立检查正确性、证据、局限和完成状态。 |

项目可以停止、恢复、跨运行时替换，并从最近一次已验证位置继续推进。

**原生 Backend：** `GitHub Copilot CLI` · `Pi` · `OpenAI Codex CLI` · `Claude Code` · `OpenCode`

## 快速安装

### 环境要求

- Python 3.11+
- Node.js 22+
- 至少一个已按官方方式安装并完成登录鉴权的 Agent CLI

### 🚀 Agent 一键接入（推荐）

> [!TIP]
> **无需手动逐条安装。** 将下面整段提示词发送给 Codex CLI、Claude Code、
> GitHub Copilot CLI、Pi 或 OpenCode。Agent 会检查环境、安装 Argus、连接当前
> backend，并运行 `argus --doctor` 验收。

```text
请阅读 https://github.com/lbx154/Argus/blob/main/docs/agent-install.md，
按照文档在我的机器上安装并配置 Argus。优先复用当前 Agent CLI 作为 Argus
backend。请实际执行环境检查、安装、配置和 argus --doctor 验证；遇到需要登录
账号、sudo、修改全局配置或其他人工授权的步骤时，先向我说明原因并等待确认。
不要要求我在对话中粘贴密码、访问令牌或 API Key。
```

Agent 将遵循 **[安装执行规范](docs/agent-install.md)**。

### 安装

```bash
git clone https://github.com/lbx154/Argus.git
cd Argus

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

### 连接后端

```bash
argus --setup --non-interactive \
  --backend copilot \
  --accept-house-rules
```

`--backend` 可使用 `copilot`、`pi`、`codex`、`claude` 或 `opencode`。

### 启动

```bash
argus
```

```bash
argus --doctor   # 检查安装与后端
argus --status   # 查看当前运行状态
```

## 交互界面

### Terminal Cockpit

```bash
argus
```

通过终端 Cockpit 与 Manager 对话、跟踪实时工作、检查状态并恢复项目。

### Web UI

启动 Argus，并在默认浏览器中打开 Web UI：

```bash
argus --web
```

默认地址：[http://127.0.0.1:8799](http://127.0.0.1:8799)

```bash
argus --web --no-open    # 只启动，不打开浏览器
argus --web --port 8800  # 使用其他端口
```

#### 通过 SSH 使用远程服务器

在服务器上：

```bash
argus --web --no-open
```

在自己的电脑上：

```bash
ssh -L 8799:127.0.0.1:8799 user@server
```

然后在本机打开 [http://127.0.0.1:8799](http://127.0.0.1:8799)。

<details>
<summary><strong>直接通过局域网访问</strong></summary>

非本机监听始终受 Bearer Token 保护：设置了 `ARGUS_SKILL_WEB_TOKEN` 就用它，没设置则为本次运行自动生成一个。

```bash
argus --web --host 0.0.0.0 --port 8799 --no-open
```

命令会打印其他设备可达的地址、Token，以及一个二维码。想让 Token 在重启后保持不变，自己设置即可：

```bash
export ARGUS_SKILL_WEB_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

如果确实要在没有 Token 的情况下提供服务（仅在你自己有鉴权代理的前提下），设置 `ARGUS_SKILL_WEB_ALLOW_INSECURE=1`。

</details>

### 在手机上使用

Telegram、飞书 / Lark 和网页版都可以在手机上使用。两个聊天机器人都是**向外拨号**的长连接，所以位于 NAT 后面的守护进程不需要内网穿透，也不需要公网地址：

```bash
# 飞书 / Lark —— WebSocket 长连接，无需配置请求地址
pip install 'argus-skill[feishu]'
export ARGUS_SKILL_ENABLE_FEISHU=1
export ARGUS_SKILL_FEISHU_APP_ID=cli_xxx ARGUS_SKILL_FEISHU_APP_SECRET=xxx

# Telegram
export ARGUS_SKILL_ENABLE_TELEGRAM=1
export ARGUS_SKILL_TELEGRAM_BOT_TOKEN=... ARGUS_SKILL_TELEGRAM_CHAT_ID=...
```

两个机器人提供完全相同的命令（`/add`、`/status`、`/nudge`、`/backlog` 等）。网页版可以添加到手机主屏幕，扫描 `argus --web --host 0.0.0.0` 打印的二维码即可完成配对。

完整配置见 **[docs/mobile.md](docs/mobile.md)**。

## 高级使用

Argus 的设计目标不是“只能配置”，而是“可以被你改变”。

### 改造整个运行时

如果你是 Agent 的狂热爱好者，我们推荐你在本地部署 Argus，让完整闭环真正适合自己的工作方式。你可以调整角色 Prompt、工作流边界、审查策略、工具与运行约定，对接已有基础设施，并用测试固定自己重视的行为。

### 创建自己的 Vertical

Vertical 可以为你的领域提供专属阶段、Skill、数据集、工具、证据要求、评测方法与完成标准。规划与审查将遵循该领域真正重要的规范，而不是一套通用流程。

#### 内置 Research Discovery

`research_discovery` 面向研究方向的早期探索，其中理论机制和真实应用问题
必须同样重要。它依次经历 `frame → discover → probe → decide`，最后产出一个
经排序的研究组合，以及一份受证据约束的 Research Bet，或一个有依据的
`no_bet` 结果。完成并不意味着定理已被证明、应用已在生产环境中可用，或论文
已经就绪；可选的交接只会命名下一项有边界的 `math`、`research` 或 `software`
任务。

Research Discovery 也可以作为动态 Seed Project 运行。一个有依据的初始化点会
扩展成自己的有界 Bet DAG：科学否定、最近工作碰撞，或同一前提下第二次无信息
probe，只会释放当前分支，并自动安排一条近域和一条远域续接路线；不相关的兄弟
分支继续推进。执行、访问、实现、评测器、资源或权限失败只触发有界修复，绝不
作为 Idea 被否定的证据。

每个项目最多允许五个活跃 Bet，同时仍由宿主级并发、费用、token、环境交互、
凭据与 compute broker 限制实际执行。系统状态可从
`research/discovery/AUTO_EXPANSION.json`、不可变的
`expansion/requests/<event_id>.json` 和类型化 Rejection Capsule 审计。Seed
Project 的数量可以动态增长；Memory-as-Control 的五个项目只是一个示例组合，
不是五种固定角色或项目类型。全自动表示在现有权限内无需逐分支批准，不会获得
新的外部权限，也不会把探索完成等同于理论证明、生产可用或论文就绪。

### 让其他 Agent 成为外层入口

你可以通过 GitHub Copilot、Pi、Codex、Claude Code、OpenCode、OpenClaw 或 Hermes 调用 Argus、检查状态、操作本地 CLI 或 Web/API，并继续迭代自己的部署。

- **Argus 原生 Backend：** GitHub Copilot CLI、Pi、Codex CLI、Claude Code、OpenCode
- **外层 Agent：** OpenClaw、Hermes，或任何能够使用 Shell / HTTP API 的 Agent

常用入口：

```bash
argus --doctor
argus --status
argus --web --no-open
```

最强大的 Argus 往往是一套被你认真改造成更适合自己伟大领域与工作方式的 Argus。

## 更新

```bash
cd Argus
git pull --ff-only
.venv/bin/python -m pip install -e .
.venv/bin/argus
```

Argus 会识别过期的本地 WebAPI 与 daemon，并在受控任务边界完成替换。

## 微信群

扫码加入 Argus 交流群。二维码有效期以图片中的提示为准；如果已经过期，请在 Issue 中联系维护者更新。

<p align="center">
  <img src="docs/assets/argus-wechat-group.jpg" width="360" alt="Argus 微信交流群二维码">
</p>
