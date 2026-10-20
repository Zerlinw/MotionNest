# 数据可信（docs/data-trust.md）

## 为什么数据是一等公民

错误信息一旦被动画包装，会显得更具权威性。因此数据来源、口径、计算、
版本、显示格式和出处披露必须是项目模型的一等公民，而不是提示词里的
一句"请注意"。

## 四道门禁

| 门禁 | 检查内容 | 失败后果 |
|---|---|---|
| 数据门 | 字典覆盖度、必填空值、数值列单位、来源、时区 | 阻止进入生成流程 |
| 逻辑门 | 叙事候选必须绑定证据 ID；指标必须可复算；必须声明忽略了什么 | 阻止 compose |
| 视觉门 | 图层 ID 唯一、文字长度、图表结构、场景时长 | 阻止 compose |
| 发布门 | 三项人工签批齐全（配乐/运镜/终审） | 阻止 export |

## 证据链

```
画面元素（scene-03-layer-01）
   ▲ 点击定位（studio/inbox.py hit_test）
镜头断言（Shot.assertion）
   ▲ 绑定（evidence_ids）
指标口径（DataDictionary.metric_definitions）
   ▲ 复算
数据行（data/snapshot/*.csv 原始行）
```

## 改数的纪律

`RevisionPatch.needs_recompute` 为 true 时（改动了 value/series/unit/total/baseline），
CLI 会明确提示：先 `mnest data verify`，再 `mnest review`，通过后才能导出。
画面看着改对了、底层数字错了——这条路径被工程上堵死。

## 版本与复现

- 每次批准生成内容寻址快照（`versions/<时间>-<状态哈希>/`）；
- `mnest undo` 整库还原；`diff_snapshots` 给出文件级差异；
- 导出时 `exports/audit.json` 记录：数据来源、门禁结果、签批人、镜头数、版本号。
