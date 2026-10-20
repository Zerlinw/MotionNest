# 工作流手册（docs/workflow.md）

## 一条完整链路（30 秒数据短片）

```bash
# 0. 环境自检
mnest doctor
mnest models check deepseek-flash     # 低成本档默认模型
mnest models routes                   # 确认各任务当前生效档位

# 1. 建项目
mnest new q3-story

# 2. 数据导入（数据门禁：缺失列/单位/来源/时区）
mnest data add ./q3.csv --project q3-story --dictionary ./dictionary.json

# 3. 数据解读 → 三个叙事方向（低成本档，全自动）
mnest plan --project q3-story

# 4. 人批准一个方向（质量的第一道人工闸门）
mnest plan --project q3-story --approve cand-1

# 5. 分镜 + 初稿动画（低成本档，两步都过 schema 校验）
mnest compose --project q3-story --duration 30000

# 6. 强模型档三项（各自需人工签发）
mnest music  --project q3-story
mnest camera --project q3-story --scene scene-01 --complexity complex
mnest review report --project q3-story

# 7. 人工签批
mnest review approve reviews/music-plan.json  --project q3-story
mnest review approve reviews/camera-moves.json --project q3-story
mnest review approve reviews/review-report.json --project q3-story

# 8. 渲染 + 导出（四道门禁 + 三项签批齐全才放行）
mnest render --project q3-story --quality final
mnest export --project q3-story
```

## 指着画面改（编辑回路）

```bash
# 用户在预览画面上点击某元素并留评论（时间点 + 坐标 + 命中图层）
mnest inbox post "这个百分比和标题不一致" --project q3-story \
  --scene scene-03 --time-ms 8200 --x 960 --y 540 --element scene-03-layer-01

# agent 侧领取 → 定点改稿 → 回报
mnest inbox next --project q3-story
mnest revise "这个百分比和标题不一致" --project q3-story \
  --scene scene-03 --layer scene-03-layer-01
mnest inbox done comment-xxxx --note "已改为 42.1%（口径：retained_d30/new_users）" --project q3-story

# 改错了？回滚到上一快照（单位是完整项目状态）
mnest undo --project q3-story
```

## 数据更新 ≠ 重做

1. 用新 CSV 重新 `mnest data add`（数据门禁重跑）；
2. `mnest plan` 重新解读，对比哪些数字改变；
3. 逐镜头 `mnest revise` 或重新 `mnest compose`；
4. 旧版本快照始终在 `versions/` 中可查、可回滚、可 diff。

## 离线模式（无密钥跑通链路）

`mnest plan --offline` 与 `mnest compose --offline` 使用确定性模板，
不调用任何模型，用于演示链路、测试基线与无网环境。
离线产出会在工件中标注"模板产出，需人工确认"。
