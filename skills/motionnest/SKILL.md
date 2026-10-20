---
name: motionnest
description: 把结构化数据或一句话需求，转成可审片、可改稿、可导出成片的数据故事动画。当用户要求"做一支数据短片 / 动画成片 / 把这份数据讲成视频 / 指着画面改"时使用本技能。
license: MIT
---

# MotionNest 技能（动巢）

MotionNest 是一套"代码即影片"的工作流：**模型负责建议，确定性程序负责计算，人负责批准**。
本技能提供方法论与命令；引擎在 `mnest` CLI 中。

## 何时使用

- 用户给出 CSV/JSON/数据结论，想要一支可发布的动画短片；
- 用户想在预览画面上"指着某一处改"；
- 用户要求数据更新后增量改片，而不是重做。

## 九步工作流（对应命令）

| 步骤 | 动作 | 命令 | 负责方 |
|---|---|---|---|
| 1 | 建项目 | `mnest new <name>` | 程序 |
| 2 | 读数据 + 口径 | `mnest data add <csv> --dictionary <json>` | 数据门禁 |
| 3 | 数据解读 → 多方向 | `mnest plan` | 低成本档模型 |
| 4 | 批准一个方向 | `mnest plan --approve cand-1` | **人** |
| 5 | 分镜脚本 | `mnest compose`（第一步） | 低成本档模型 |
| 6 | 初稿动画场景树 | `mnest compose`（第二步） | 低成本档模型 |
| 7 | 配乐 / 运镜 | `mnest music` / `mnest camera` | 强模型档 + **人工签发** |
| 8 | 终审校对 | `mnest review report` | 强模型档 + **人工签发** |
| 9 | 渲染导出 | `mnest render` / `mnest export` | 程序（门禁把关） |

## 不可违反的规则

1. **数字不出自模型**：一切数值来自数据快照与确定性计算；模型只做解读与呈现，
   不得创造或修改数据（改动数据承载属性会自动标记 needs_recompute 并重过数据门）。
2. **每个画面可追溯**：镜头必须绑定证据 ID；点击元素必须能回到数据点、口径与来源。
3. **叙事不是唯一解释**：每个方向必须声明"刻意忽略了什么"。
4. **审美分层**：模型没有听觉，配乐只规划节拍/能量结构；终听必须人来。
5. **未签批不导出**：`reviews/music-plan.json`、`reviews/camera-moves.json`、
   `reviews/review-report.json` 三份工件缺一，发布门禁即拦截。
6. **定点改稿**：评论必须定位到 场景/图层/数据点；只改目标属性，无关场景不重建。

## 指着画面改（编辑回路）

```
用户在预览画面点击并留评论（时间点 + 坐标 + 命中图层）
   → mnest inbox post
   → mnest inbox next            # agent 领取
   → mnest revise "评论" --scene scene-01 --layer scene-01-layer-01
   → mnest inbox done <id> --note "改了什么"
   → 受影响镜头增量重渲，版本可 mnest undo 回滚
```

## 模型档位策略（无需硬编码）

- 低成本档（默认 `deepseek-flash`）：数据解读、分镜、初稿动画、改稿 —— 全自动；
- 强模型档（默认 `deepseek-v4-pro`）：配乐审美、复杂三维运镜、终审 —— 需人工签发；
- 强模型不可用时自动降级为低档草案并标记 `需人工签发`；两者皆不可用则转人工兜底队列。

规则集中在 `config/router.yaml`，换模型只改 `config/models.yaml`。

## 交付前自检

1. `mnest data verify` —— 数据门禁必须通过；
2. `mnest review report` —— 无 blocking 问题；
3. 按正常速度看一遍全片（人看，或派独立 agent 冷审）；
4. `mnest export` —— 四道门禁 + 三项签批齐全才会产出成片与审计清单。

## 边界声明

本技能只借鉴公开可描述的方法论（工件化、规则化、定点改稿、版本沉淀），
不复制任何第三方项目的代码、素材、角色形象、文案或私有格式。
