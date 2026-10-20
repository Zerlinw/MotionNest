# 架构总览（docs/architecture.md）

## 设计主线

> **模型负责建议，确定性程序负责计算，人负责批准。**

三条不可动摇的隔离：

1. **模型 ↔ 计算隔离**：LLM 的一切产出先进入"提议区"（Pydantic schema 校验），
   通过后才进入执行区；数值永远来自数据快照与确定性计算，不由模型创造。
2. **模型 ↔ 业务隔离**：业务代码只依赖 `TaskRouter` 一个入口，
   不 import 任何 Provider；切换模型 = 改 YAML，不改代码。
3. **自动化 ↔ 责任隔离**：低成本档任务全自动；强模型档任务与发布动作
   始终保留人工签发位（发布门禁强制检查）。

## 四层架构

```
┌─────────────────────────────────────────────────────────────┐
│ Agent 编排层（agents/）                                       │
│   DataInterpreter  StoryboardAgent  Animator  Reviser        │
│   MusicDirector    CameraDesigner   FinalReviewer            │
│   只调用 TaskRouter.complete(task, messages)                  │
├─────────────────────────────────────────────────────────────┤
│ 模型抽象层（llm/）                                            │
│   TaskRouter ──► ModelRegistry ──► LLMProvider               │
│                                    ├── OpenAIProvider        │
│                                    └── AnthropicProvider     │
│   规则来自 config/router.yaml + config/models.yaml            │
├─────────────────────────────────────────────────────────────┤
│ 确定性层（core/ data/ composition/ qa/）                       │
│   项目状态与版本 · 数据快照/字典/门禁 · 时间轴/场景树 · 四道门禁 │
├─────────────────────────────────────────────────────────────┤
│ 呈现层（runtime/ studio/ cli/）                                │
│   HTML 场景渲染 · playwright 逐帧 · FFmpeg 合成 · 评论收件箱   │
└─────────────────────────────────────────────────────────────┘
```

## 模块职责表

| 模块 | 职责 | 关键契约 |
|---|---|---|
| `llm/base.py` `llm/openai_provider.py` `llm/anthropic_provider.py` | 双接口格式归一化：`chat() -> LLMResponse`，含重试/密钥/健康检查 | 业务层只见 `Message` 与 `LLMResponse` |
| `llm/registry.py` | 模型声明（逻辑名/模型 ID/格式/端点/密钥环境变量/档位）→ Provider 工厂与缓存 | `models.yaml` 一段声明 = 一个可用模型 |
| `llm/router.py` | 任务 → 档位 → 模型的决策与调用；降级标记；人工兜底；审计流水 | `complete(task, messages) -> RoutedResponse` |
| `agents/` | 七个业务 Agent：四个低成本档自动任务 + 三个强模型档人工签发任务 | 只依赖 `TaskRouter`；输出必须过 schema |
| `core/schemas.py` | 全链路 Pydantic 模型（数据/脚本/合成/声音/运镜/审片/改稿/清单） | 模型输出的唯一合法形态 |
| `core/project.py` `core/versions.py` | 项目工作区；内容寻址快照、整体还原、文件级 diff、人工签批 | 回滚单位 = 完整项目状态 |
| `data/` | CSV/JSON 加载、类型推断、摘要、数据字典、数据门禁 | 给模型看"目录"而非全量 |
| `composition/` | 时间轴（帧时钟）、场景树纯函数、定点补丁 | 给定状态任意帧号稳定复现 |
| `qa/gates.py` | 四道门禁：数据 → 逻辑 → 视觉 → 发布 | 任一门禁失败不得自动导出 |
| `runtime/renderer.py` `runtime/ffmpeg.py` | Composition → HTML 场景 →（可选逐帧）→ MP4；FFmpeg 受控子进程 | 图层稳定 `data-mn-id`；缺工具降级不报错 |
| `studio/inbox.py` | 评论收件箱：坐标命中测试、状态机（open→claimed→resolved） | append-only JSONL，可审计 |
| `cli.py` | `mnest` 命令：把上述模块串成工作流 | 每个命令一个明确工件产出 |

## 数据流（一次生成的旅程）

```
CSV/JSON ──► data/（快照+字典+摘要）──► 数据门禁 ──► plan/（洞察+方向）
   │                                                    │ 人批准
   │                                                    ▼
   │                                          script/（分镜：时间码+断言+证据）
   │                                                    │
   │                                    composition/（场景树 JSON + HTML）
   │                                                    │
   │              reviews/（配乐/运镜/终审，强模型+人工签发）│
   │                                                    ▼
   └──────────────────────────────────────────► exports/（成片+审计清单）
```

## 关键不变量

1. **ID 稳定性**：`scene-NN` / `scene-NN-layer-MM` 全局唯一——定点改稿、
   坐标命中、diff 定位全部依赖它；视觉门禁强制检查。
2. **证据绑定**：镜头 `assertion` ↔ `evidence_ids` ↔ 指标 `evidence_id` ↔
   数据行；逻辑门禁检查每个叙事候选至少绑定一个证据。
3. **版本可复现**：每次批准生成内容寻址快照；`undo` 整库还原；
   导出时写入数据快照、口径、签批与门禁结果。
4. **降级可见**：任何非首选档位的产出都带 `degraded=true` 与
   `requires_human_signoff=true`，静默降级不存在。
