# 示例：XR-500 工业巡检机器人 · 30 秒宣传片

自造合成素材（文档 + 参数表 + 迷你 pptx + 两张图片），用于跑通 MotionNest
宣传片管线。不包含任何真实业务数据。

## 一键跑通（CLI）

```bash
cd <仓库根目录>

# 重新生成素材（可选，仓库已附带生成结果）
python scripts/make_example_pptx.py

# 文档 → 30 秒 MP4（未配置模型时自动模板降级，仍可出片）
mnest promo examples/equipment-promo/product.md examples/equipment-promo/specs.csv \
  examples/equipment-promo/docs/product-deck.pptx \
  --assets examples/equipment-promo/assets \
  --note "突出续航与防护，面向海外采购客户" \
  -o out
```

产物：`out/promo-*/exports/promo.mp4`（1920×1080@30fps，30.00s）
与 `exports/audit.json`（数据来源 / 素材命中 / 时长校验）。

## 桌面端

启动 MotionNestDesktop.exe，把 `product.md`、`specs.csv`、
`docs/product-deck.pptx` 与 `assets/` 文件夹一起拖入工作台，
点击"生成 30 秒宣传片"。

## 质量说明

- 未配置对话模型：要点蒸馏与文案走确定性模板（审计中注明 template）；
- 配置 DeepSeek 密钥后自动切换模型链路（蒸馏 + 文案两次调用）；
- 未配置生图模型：缺图镜头以 SVG/CSS 图形兜底；配置后按需补图。
