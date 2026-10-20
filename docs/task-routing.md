# 任务路由规则（docs/task-routing.md）

## 路由决策流程

```
resolve(task):
  1. 按 rule.candidates 顺序找"首选档位且密钥可用"的模型 → 命中即用（degraded=false）
  2. 按 rule.fallback_tiers 顺序找"档位默认模型且密钥可用" → 降级使用（degraded=true）
  3. 全部不可用：
     ├── rule.human_review=true  → 抛 HumanReviewRequired（转人工兜底队列）
     └── rule.human_review=false → 抛 ModelUnavailableError（明确失败，不静默）
```

## 任务分档表（config/router.yaml）

| 任务 | 首选档位 | 候选模型 | 回退 | 人工签发 | 说明 |
|---|---|---|---|---|---|
| `data_interpretation` | low | deepseek-flash | — | 否 | 字段理解、指标摘要、异常发现 |
| `storyboard_generation` | low | deepseek-flash | strong | 否 | 逐镜头时间码 + 数据断言 |
| `draft_animation` | low | deepseek-flash | strong | 否 | 场景树/图层/动画原语 |
| `animation_revision` | low | deepseek-flash | strong | 否 | 按评论定点修改 |
| `music_aesthetics` | strong | deepseek-v4-pro | low | **是** | 模型无听觉，终听必须人工 |
| `camera_3d_design` | strong | deepseek-v4-pro | low | **是** | 简单运镜走确定性模板，不耗模型 |
| `final_review` | strong | deepseek-v4-pro | low | **是** | 数字一致性/披露/节奏校对 |

## 分工原则（为什么这样分）

1. **可校验的上低成本档**：结构化、可 schema 校验、错了能测出来的任务，
   用 deepseek-flash 全自动完成，靠四道门禁兜底质量。
2. **审美与终审上强模型档**：配乐审美、复杂运镜、成片校对没有确定性对错，
   用强模型提升上限，但**永不自动放行**——三项产出必须人工签批。
3. **人工兜底是机制不是口号**：强模型不可用时
   （a）低档模型出草案并标记 `degraded + requires_human_signoff`；
   （b）两者皆无时任务进入 `reviews/human-queue.json`，由人完成该环节。
   发布门禁会拦住任何未签批工件。

## 调整路由的两种方式

- **换模型**：改 `config/models.yaml`（不动路由）；
- **换分工**：改 `config/router.yaml` 的 `preferred_tier / candidates / fallback_tiers / human_review`。

两种改动都不触碰 `src/motionnest/agents/` 下任何业务代码。
