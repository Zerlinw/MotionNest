# 示例：Q3 用户增长数据故事（q3-retention）

自造合成数据 + 数据字典，用于跑通 MotionNest 全链路。不包含任何真实业务数据。

## 一键跑通（无需模型密钥，离线模板模式）

```bash
cd <仓库根目录>

# 1. 创建项目
mnest new q3-story --path examples/q3-retention

# 2. 导入数据并过数据门禁
mnest data add examples/q3-retention/data/q3.csv \
  --project examples/q3-retention/q3-story \
  --dictionary examples/q3-retention/data/dictionary.json

# 3. 数据解读（离线模板）并批准一个方向
mnest plan --project examples/q3-retention/q3-story --offline --approve cand-1

# 4. 分镜 + 初稿动画（离线模板）
mnest compose --project examples/q3-retention/q3-story --offline --duration 24000

# 5. 本机渲染 HTML 场景（安装 motionnest[render] 后可出 MP4）
mnest render --project examples/q3-retention/q3-story

# 6. 在画面上留一条评论并定点改稿
mnest inbox post "标题文字太长，超出安全区" \
  --project examples/q3-retention/q3-story \
  --scene scene-01 --time-ms 1500 --x 100 --y 120 --element scene-01-layer-01
mnest inbox list --project examples/q3-retention/q3-story
```

配置 `DEEPSEEK_API_KEY` 后，去掉 `--offline` 即可切换为低成本档模型链路；
强模型档任务（配乐/运镜/终审）需要 `deepseek-v4-pro` 可用或人工兜底。
