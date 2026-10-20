# MotionNest · 动巢

[中文](README.md) · [English](README.en.md)

<p align="center">
  <strong>把一张可信的数据表，变成可审片、可改稿、可导出成片的数据故事动画。</strong>
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=flat-square">
  <a href="CHANGELOG.md"><img alt="Version 0.3.0" src="https://img.shields.io/badge/version-0.3.0-blueviolet.svg?style=flat-square"></a>
  <a href="tests"><img alt="Tests: 106 passed" src="https://img.shields.io/badge/tests-106%20passed-brightgreen.svg?style=flat-square"></a>
  <img alt="Platform: Windows / macOS / Linux" src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg?style=flat-square">
  <a href="CONTRIBUTING.md"><img alt="PRs welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square"></a>
</p>

> 模型负责建议，确定性程序负责计算，人负责批准。
> 每一个会动的画面，都能回到一个数字、一条证据和一个版本。

MotionNest 有两条产线，共用同一套逐帧渲染与 FFmpeg 编码底座：

- **宣传片（promo，推荐）**：把 Markdown / CSV / PPTX 文档与素材文件夹直接喂进来，
  LLM 蒸馏要点、固定骨架分镜、画面合成，逐帧渲染成 **30 秒 1920×1080 MP4**；
  没有密钥时自动降级为确定性模板，仍可出片。
- **数据故事（data-story）**：输入结构化数据与数据字典，Agent 完成数据解读、叙事方向、
  分镜脚本、初稿动画与定点改稿；强模型档负责审美与终审，人工签批后导出，数字可追溯。

**它不是"一句话抽卡出片"工具**——宣传片有固定 30 秒骨架与素材/文案审计；
数据故事链路还额外提供证据绑定、评论定位与版本回滚。

---

## 目录

- [核心特性](#核心特性)
- [架构总览](#架构总览)
- [模型档位与任务路由](#模型档位与任务路由)
- [快速开始](#快速开始)
- [桌面工具（exe）](#桌面工具exe)
- [配置示例](#配置示例)
- [CLI 参考](#cli-参考)
- [项目结构](#项目结构)
- [四道质量门禁](#四道质量门禁)
- [开发与测试](#开发与测试)
- [路线图](#路线图)
- [合规与许可](#合规与许可)

---

## 核心特性

- **模型层可插拔**：Provider / Registry / Router 三件套抽象，默认兼容
  **OpenAI 与 Anthropic 两种接口格式**；新增模型只改 YAML，业务代码零改动。
- **双档位分工**：低成本档 `deepseek-flash`（DeepSeek V4.1 Flash）承担数据解读、
  分镜脚本、初稿动画、动画改稿；强模型档 `deepseek-v4-pro` 承担配乐审美、
  复杂三维运镜、成片终审，产出必须人工签发。
- **人工兜底是机制**：强模型不可用时自动降级为低档草案并标记签批要求；
  两者皆不可用时任务进入人工兜底队列，发布门禁拦截任何未签批工件。
- **数据可信**：数据快照、数据字典、口径与来源是一等公民；证据 ID 把
  画面元素 → 镜头断言 → 指标口径 → 数据行 串成可复算链路。
- **帧帧可审可改**：场景树是唯一事实源，图层带稳定 ID；评论携带时间点与坐标，
  命中测试定位图层；定点补丁只改目标属性，无关场景不重建。
- **可回滚的版本**：每次批准生成内容寻址快照，`mnest undo` 整库还原，
  导出时写入审计清单（数据来源、门禁结果、签批人、版本号）。
- **本机渲染**：Composition JSON → HTML 场景 →（可选 Playwright 逐帧）→ FFmpeg MP4；
  未装渲染依赖时自动降级为 HTML + 清单，不阻塞工作流。

## 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│ Agent 编排层（src/motionnest/agents/）                         │
│  DataInterpreter · StoryboardAgent · Animator · Reviser       │
│  MusicDirector · CameraDesigner · FinalReviewer               │
│  只调用 TaskRouter.complete(task, messages)                    │
├──────────────────────────────────────────────────────────────┤
│ 模型抽象层（src/motionnest/llm/）                              │
│  TaskRouter ──► ModelRegistry ──► LLMProvider                 │
│                                  ├── OpenAIProvider           │
│                                  └── AnthropicProvider        │
│  规则：config/router.yaml + config/models.yaml                 │
├──────────────────────────────────────────────────────────────┤
│ 确定性层（core/ data/ composition/ qa/）                       │
│  项目状态与版本 · 数据快照/门禁 · 时间轴/场景树 · 四道门禁       │
├──────────────────────────────────────────────────────────────┤
│ 呈现层（runtime/ studio/ cli/）                                │
│  HTML 场景 · 逐帧渲染 · FFmpeg 合成 · 评论收件箱 · mnest CLI    │
└──────────────────────────────────────────────────────────────┘
```

模块职责的完整说明见 [docs/architecture.md](docs/architecture.md)，
模型抽象层设计见 [docs/model-layer.md](docs/model-layer.md)。

## 模型档位与任务路由

| 任务 | 档位 | 默认模型 | 人工签发 | 说明 |
|---|---|---|---|---|
| 数据解读 `data_interpretation` | low | `deepseek-flash` | 否 | 字段理解、指标摘要、叙事候选 |
| 分镜脚本 `storyboard_generation` | low | `deepseek-flash` | 否 | 逐镜头时间码 + 数据断言 + 证据绑定 |
| 初稿动画 `draft_animation` | low | `deepseek-flash` | 否 | 场景树、图层、动画原语 |
| 动画改稿 `animation_revision` | low | `deepseek-flash` | 否 | 评论 → 定点补丁 |
| 配乐审美 `music_aesthetics` | strong | `deepseek-v4-pro` | **是** | 模型无听觉，只规划节拍/能量结构 |
| 三维运镜 `camera_3d_design` | strong | `deepseek-v4-pro` | **是** | 简单运镜走确定性模板，复杂才用强模型 |
| 成片终审 `final_review` | strong | `deepseek-v4-pro` | **是** | 数字一致性、披露、节奏校对 |

路由规则完整说明见 [docs/task-routing.md](docs/task-routing.md)。

## 快速开始

### 1. 安装

```bash
git clone https://github.com/<your-org>/motionnest.git
cd motionnest

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # 需要逐帧渲染时加 [render]
```

环境要求：Python ≥ 3.10；可选 FFmpeg（视频编码）；可选 Playwright + Chromium（逐帧渲染）。

### 2. 配置密钥

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key（https://platform.deepseek.com 申请）
#   DEEPSEEK_API_KEY=sk-xxx
```

### 3. 环境与模型自检

```bash
mnest doctor                      # Python/FFmpeg/Playwright/配置/密钥
mnest models list                 # 注册表中的模型与档位
mnest models check deepseek-flash # 真实调用探测（消耗微量额度）
python scripts/verify_deepseek.py # DeepSeek 双接口格式分级验证
```

### 4. 跑通示例（离线模式，无需密钥）

```bash
mnest new q3-story --path examples/q3-retention
mnest data add examples/q3-retention/data/q3.csv \
  --project examples/q3-retention/q3-story \
  --dictionary examples/q3-retention/data/dictionary.json
mnest plan  --project examples/q3-retention/q3-story --offline --approve cand-1
mnest compose --project examples/q3-retention/q3-story --offline --duration 24000
mnest render  --project examples/q3-retention/q3-story
```

配置密钥后去掉 `--offline`，即切换为低成本档模型链路。

## 宣传片管线（文档 → 30 秒 MP4）

```bash
# 安装（真实出片需要 FFmpeg 在 PATH + Playwright；浏览器可复用系统 Edge/Chrome）
pip install -e ".[promo]"

# 文档进 → 成片出（未配置模型时自动模板降级）
mnest promo examples/equipment-promo/product.md \
  examples/equipment-promo/specs.csv \
  examples/equipment-promo/docs/product-deck.pptx \
  --assets examples/equipment-promo/assets \
  --note "突出续航与防护，面向海外采购客户" \
  -o out

# 产物
#   out/promo-*/exports/promo.mp4       30.00s / 1920×1080 / 30fps
#   out/promo-*/exports/audit.json      来源、素材命中、时长与帧数校验
```

管线六阶段（`src/motionnest/promo/`）：

1. **解析**：md / csv / json / pptx → 文本块、表格摘要、图片（pptx 内嵌图自动提取）；
2. **蒸馏**：LLM 产出产品名 / 标语 / 卖点 / 佐证数字 / CTA；失败降级模板；
3. **分镜**：固定骨架（钩子 3s + 亮相 5s + 卖点 15s + 佐证 4s + CTA 3s），总时长精确 30000ms；
4. **合成**：素材关键词匹配 > AI 生图 > 图形兜底，输出 Composition 场景树；
5. **渲染**：HTML 场景 → Playwright 逐帧 → FFmpeg H.264 MP4；
6. **校验导出**：帧数 + ffprobe 时长硬校验，写 `exports/promo.mp4` 与 `audit.json`。

## 桌面工具（exe）

DeepSeek 客户端风格的两页界面：**工作台**（拖入 md/csv/pptx/图片/文件夹 → 一句话补充 →
生成 30 秒宣传片）与**设置**（对话模型 / 生图模型 / 主题）。生成在后台线程执行，
底部控制台实时输出日志，完成后可直接播放或打开所在文件夹。

```bash
# 开发模式
pip install -e ".[desktop,render]"
python -m desktop                 # 启动 GUI
python -m desktop --selfcheck     # 无头自检
python -m desktop --render-selftest  # 逐帧渲染自检（1s 场景 → MP4）

# 打包为免 Python 环境依赖的 exe
pip install pyinstaller PySide6
python scripts/build_exe.py --verify   # 产出 dist/MotionNestDesktop.exe 并自检
```

exe 为绿色模式：设置保存在 exe 同级 `motionnest-settings.json`；`config/` 随包分发。
真实出片需要 FFmpeg 在 PATH 与 Playwright Python 包；浏览器默认回退到系统 Edge/Chrome，
也可用 `MNEST_BROWSER_CHANNEL=msedge/chrome` 显式指定，避免把 Chromium 打进 exe。

## 配置示例

### 模型注册（`config/models.yaml` 节选）

```yaml
models:
  - name: deepseek-flash            # 逻辑名：路由规则只认它
    model_id: deepseek-flash        # DeepSeek V4.1 Flash
    provider_format: openai         # OpenAI 兼容端点
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY
    tier: low
    max_output_tokens: 8192

  - name: deepseek-v4-pro
    model_id: deepseek-v4-pro
    provider_format: openai
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY
    tier: strong
```

### 同一个模型，Anthropic 接口格式

```yaml
  - name: deepseek-flash-anthropic
    model_id: deepseek-flash
    provider_format: anthropic      # 自动拼 /v1/messages
    base_url: https://api.deepseek.com/anthropic
    api_key_env: DEEPSEEK_API_KEY
    tier: low
```

### 任务路由（`config/router.yaml` 节选）

```yaml
routes:
  storyboard_generation:            # 低成本档：首选 → 强档回退 → 失败即报错
    preferred_tier: low
    candidates: [deepseek-flash]
    fallback_tiers: [strong]
    human_review: false

  music_aesthetics:                 # 强模型档：低档出草案 + 人工签发；全不可用 → 人工兜底
    preferred_tier: strong
    candidates: [deepseek-v4-pro]
    fallback_tiers: [low]
    human_review: true
```

## CLI 参考

| 命令 | 用途 |
|---|---|
| `mnest promo <文档...> [-o out] [--assets DIR] [--quality preview\|final]` | **宣传片：md/csv/pptx → 30 秒 MP4（全自动）** |
| `mnest doctor` | 环境检查（Python/FFmpeg/Playwright/配置/密钥） |
| `mnest models list\|check\|routes` | 模型清单 / 真实探测 / 路由表 |
| `mnest new <name>` | 创建项目工作区 |
| `mnest data add\|verify` | 数据导入（过数据门禁）/ 重跑门禁 |
| `mnest plan [--approve ID] [--offline]` | 数据解读 → 叙事候选 → 人批准 |
| `mnest compose [--offline]` | 分镜脚本 + 初稿动画场景树 |
| `mnest revise "评论" --scene --layer` | 定点改稿（自动判定是否触及数据层） |
| `mnest music\|camera` | 配乐规划 / 三维运镜（强模型档） |
| `mnest review report\|approve` | 成片终审 / 人工签批 |
| `mnest render [--quality preview\|final]` | HTML 场景 →（可选逐帧）→ MP4 |
| `mnest export` | 四道门禁 + 三项签批 → 成片 + 审计清单 |
| `mnest inbox post\|list\|next\|done` | 评论收件箱（指着画面改） |
| `mnest undo\|audit` | 回滚到上一快照 / 版本与调用审计 |

## 项目结构

```
motionnest/
├── README.md / README.en.md      # 项目说明（中/英）
├── LICENSE / THIRD_PARTY.md      # MIT；第三方资产许可清单
├── CONTRIBUTING.md / SECURITY.md / CHANGELOG.md
├── pyproject.toml                # 打包、依赖、CLI 入口 mnest
├── config/
│   ├── models.yaml               # 模型注册表（逻辑名/ID/格式/端点/密钥/档位）
│   └── router.yaml               # 任务路由规则（档位/候选/回退/人工签发）
├── src/motionnest/
│   ├── cli.py                    # mnest 命令：工作流编排
│   ├── settings.py               # 配置定位与 Registry/Router 构建
│   ├── llm/                      # 模型抽象层
│   │   ├── base.py               #   LLMProvider 抽象（重试/密钥/健康检查）
│   │   ├── openai_provider.py    #   OpenAI 兼容（/chat/completions）
│   │   ├── anthropic_provider.py #   Anthropic 兼容（/v1/messages）
│   │   ├── registry.py           #   ModelSpec + Provider 工厂/缓存
│   │   └── router.py             #   TaskRouter：档位决策/降级/人工兜底/审计
│   ├── agents/                   # Agent 业务层（只依赖 TaskRouter）
│   │   ├── prompts.py            #   提示词仓库（可覆盖，桌面端可编辑）
│   │   ├── data_interpreter.py   #   数据解读（low）
│   │   ├── storyboard.py         #   分镜脚本（low）
│   │   ├── animator.py           #   初稿动画（low）
│   │   ├── reviser.py            #   动画改稿（low）
│   │   ├── music_director.py     #   配乐审美（strong + 人工）
│   │   ├── camera_designer.py    #   三维运镜（strong + 人工；简单走模板）
│   │   └── final_reviewer.py     #   成片终审（strong + 人工）
│   ├── core/                     # 项目状态 / 版本快照 / 全链路 schema
│   ├── data/                     # 加载 / 摘要 / 数据字典 / 数据门禁
│   ├── composition/              # 时间轴 / 场景树 / 定点补丁
│   ├── promo/                    # 宣传片管线：解析→蒸馏→分镜→合成→渲染→导出
│   ├── runtime/                  # HTML 场景 / 逐帧渲染 / FFmpeg
│   ├── studio/                   # 评论收件箱 / 坐标命中
│   └── qa/                       # 四道质量门禁（数据故事链路）
├── desktop/                      # 桌面工具（PySide6，IDEA 双主题）
│   ├── app.py                    #   主窗口：工具栏/工具窗/页面堆叠/控制台
│   ├── theme.py                  #   Darcula / IntelliJ Light 调色板与 QSS
│   ├── bridge.py                 #   桌面端 → motionnest 操作封装
│   ├── settings.py               #   可配置参数持久化（绿色模式/APPDATA）
│   ├── workers.py                #   后台线程
│   ├── console.py                #   Run 工具窗风格控制台
│   └── pages/                    #   工作台 / 设置
├── skills/motionnest/            # Agent Skills 协议入口（SKILL.md + 方法论文档）
├── templates/                    # 起步模板（只含约束，不含数字）
├── examples/q3-retention/        # 自造示例数据 + 一键跑通说明
├── docs/                         # 架构 / 模型层 / 路由 / 工作流 / 数据可信 / 许可
├── scripts/verify_deepseek.py    # DeepSeek 双接口格式分级验证
└── tests/                        # 单元 + 集成（MockTransport/StubProvider，无网络依赖）
```

## 四道质量门禁

| 门禁 | 内容 | 拦截点 |
|---|---|---|
| 数据门 | 字典覆盖、必填空值、单位、来源、时区 | 生成前 |
| 逻辑门 | 证据绑定、可复算、声明忽略信息 | compose 前 |
| 视觉门 | 图层 ID 唯一、文字长度、图表结构 | compose 后 |
| 发布门 | 三项人工签批齐全 | export |

任一门禁失败不得自动导出正式版本——门禁输出可操作错误，不是模糊警告。

> 宣传片链路（`mnest promo`）是独立的全自动产线，不走这四道门禁；它用
> 「固定 30 秒骨架 + 帧数校验 + ffprobe 时长复核 + `exports/audit.json`」保证可交付性。

## 开发与测试

```bash
pip install -e ".[dev]"
pytest                       # 全量：路由/线协议/Agent 契约/门禁/集成/promo/桌面
ruff check src tests         # lint
```

测试不依赖网络：Provider 线协议用 `httpx.MockTransport`，模型调用用 `StubProvider`，
覆盖 OpenAI/Anthropic 双格式的 URL、请求头、载荷与响应解析。

## 路线图

- [x] 模型抽象层：双接口格式 + 档位路由 + 人工兜底 + 审计
- [x] 低成本档四项任务：数据解读 / 分镜 / 初稿动画 / 改稿
- [x] 强模型档三项任务 + 人工签批 + 发布门禁
- [x] 离线模板链路（无密钥跑通）+ 示例数据
- [ ] Playwright 逐帧渲染的多画幅（16:9 / 9:16 / 1:1）
- [ ] studio 浏览器编辑器（播放 / 点选 / 拖值 / 评论）
- [ ] TTS 口播与字幕轨、用户授权音乐接入
- [ ] API/数据库连接器与协作评论

## 合规与许可

源代码 MIT（见 [LICENSE](LICENSE)）。MIT **不覆盖**用户上传的数据、字体、图像、音频、
Logo 与商标，也不覆盖第三方依赖与外部模型服务条款（见 [THIRD_PARTY.md](THIRD_PARTY.md)）。

本项目只借鉴公开可描述的工作流方法论（工件化拆分、规则化约束、先规划后渲染、
定点改稿、版本沉淀），不复制任何第三方项目的代码、素材、角色形象、文案或私有格式。
面向金融、医疗、法律、公共政策等高风险领域，本项目只提供可视化与叙事辅助，
不替代专业意见。
