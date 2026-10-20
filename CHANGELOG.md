# 变更日志（CHANGELOG.md）

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [0.3.0] - 2026-10-20

宣传片重构：文档进、30 秒 MP4 出（promo 管线），桌面端改为 DeepSeek 客户端风格。

### Added

- **promo 管线（src/motionnest/promo/）**：md/csv/json/pptx 解析与素材归一化、
  LLM 要点蒸馏（失败降级模板）、固定骨架分镜（总时长精确 30000ms）、
  画面合成与 image 图层、逐帧渲染 + ffprobe 时长校验、全自动审计导出；
- **`mnest promo` CLI**：文档列表 + 素材文件夹 + 一句话补充 → `exports/promo.mp4`；
- **桌面端重写**为「工作台 / 设置」两页（DeepSeek 客户端风格），支持拖放与后台生成；
- **示例工程** `examples/equipment-promo`（md + csv + pptx + 图片）。

### Fixed

- intake 裸图片名未归一化为 `assets/` 前缀，导致逐帧渲染图片 404；
- 逐场景 `int(ms/1000*fps)` 截断在 3750ms 镜头丢帧（4 卖点时 898/147 帧），
  改为累计取整：30s@30fps 严格 900 帧、@5fps 严格 150 帧；
- 渲染前清理旧帧，避免帧数校验把上一轮残留算进来。

### Changed

- PyInstaller 打包改用 `collect_submodules('motionnest'/'desktop')`；Playwright
  驱动按需打包，浏览器优先走系统 Edge/Chrome（channel 回退），不塞 Chromium；
- 新增 pytest 回归：promo CLI 接线、帧数精确分配、裸素材名归一化。

## [0.2.1] - 2026-10-19

界面布局重构：放大控件、统一间距对齐、低分辨率不截断。

### Changed

- **全局控件放大**：输入框/下拉/微调框/按钮最小高度 22 → 30px，内边距加大；
  表格项与表头、导航项、分组框、选项卡、工具提示同步放大；基础字号保持 13px
  （符合 IDEA 规范），标签与标题分级更清晰。
- **窗口与侧栏**：默认尺寸 1280×820 → 1480×920，最小 1080×700 → 1240×760；
  侧栏 220 → 264px；控制台停靠窗默认高度 260px。
- **设置页表格重排**：列宽策略改为"只读列内容自适应 + 可编辑列按权重拉伸"，
  模型 ID / 服务地址 / API Key 不再截断；行高 44px；整页加入滚动区。
- **表单统一规范**：标签右对齐、字段扩展填充（ExpandingFieldsGrow）、
  行距 12–16px；快速开始页卡片内边距 16 → 20px，卡片间距 12 → 16px。
- **响应式保证**：快速开始页与设置页均可滚动；1280×800 下全部内容完整显示
  （双主题已截图验证）。

## [0.2.0] - 2026-10-19

桌面工具与提示词可编辑化：快速开始流程封装为 IDEA 风格 GUI，可打包为免环境依赖的 exe。

### Added

- **桌面工具（desktop/，PySide6）**
  - IntelliJ IDEA 风格双主题：Darcula（面板 #3C3F41 / 强调蓝 #4A88C7）与
    IntelliJ Light（面板 #F2F2F2 / 强调蓝 #3574F0），工具栏一键切换并持久化；
  - 快速开始七步向导：环境自检 / 创建项目 / 导入数据 / 数据解读与批准 /
    分镜初稿 / 配乐运镜 / 终审渲染导出，与 README 快速开始一一对应；
  - 设置页（可配置参数）：API Key（密码框）、服务地址、模型 ID、超时/重试、
    人工兜底开关；保存即生效（写入环境变量 + 重建注册表）；
  - Prompt 页（可变参数）：七个任务的系统提示词与用户提示词模板编辑、
    保存覆盖、恢复默认；
  - 对话页（可变参数）：模型选择、系统提示词编辑、多轮对话（档位/延迟/token）；
  - Run 工具窗风格控制台：分级着色、自动滚动、清空/复制；
  - 绿色模式：设置存于 exe 同级 `motionnest-settings.json`，也支持
    `%APPDATA%/MotionNest/settings.json` 与 `MNEST_DESKTOP_SETTINGS` 覆盖。
- **提示词仓库（agents/prompts.py）**：七个任务的默认提示词与运行时覆盖机制，
  桌面端编辑无需改代码；Agent 基类支持实例级覆盖。
- **打包脚本（scripts/build_exe.py）**：PyInstaller onefile + windowed，
  产出 `dist/MotionNestDesktop.exe`（约 55MB，双击即运行）；
  `--selfcheck` 无头自检（含 exe 内验证），报告写入 exe 同级。
- **settings 冻结态支持**：exe 内自动发现随包分发的 `config/`。
- **测试扩充至 55 个**：新增提示词覆盖、桌面设置存储、桌面 Bridge
  （覆盖生效 / 离线全链路 / 人工兜底 / 发布门禁拦截）测试。

### Changed

- 七个 Agent 改从 `prompts` 仓库取提示词（行为不变，默认值逐字保留）。

## [0.1.0] - 2026-10-19

首个可运行版本：模型层可插拔 + 双档位路由 + 可信链路 + 本机渲染骨架。

### Added

- **模型抽象层（llm/）**
  - `LLMProvider` 抽象基类：重试（429/5xx 指数退避）、密钥读取、健康检查；
  - `OpenAIProvider`（`/chat/completions`）与 `AnthropicProvider`（`/v1/messages`）
    双接口格式，对上层完全归一化；
  - `ModelRegistry`：YAML 声明 → Provider 工厂与缓存，新增模型零代码改动；
  - `TaskRouter`：任务 → 档位 → 模型；降级标记、人工兜底、调用审计流水。
- **默认模型配置**：低成本档 `deepseek-flash`（DeepSeek V4.1 Flash）、
  强模型档 `deepseek-v4-pro`；含 Anthropic 兼容端点接入示例。
- **七个业务 Agent**
  - 低成本档（全自动）：数据解读、分镜脚本、初稿动画、动画改稿；
  - 强模型档（人工签发）：配乐审美、三维运镜（简单走确定性模板）、成片终审。
- **确定性层**：项目工作区、内容寻址快照与回滚、数据加载/摘要/数据门禁、
  时间轴、场景树与定点补丁、四道质量门禁。
- **呈现层**：HTML 场景渲染器（稳定图层 ID + CSS 动画可 seek）、
  Playwright 逐帧渲染（可选）、FFmpeg 编码、评论收件箱（坐标命中测试）。
- **CLI（mnest）**：doctor / models / new / data / plan / compose / revise /
  music / camera / review / render / export / inbox / undo / audit。
- **离线模板链路**：`--offline` 参数使 plan/compose 不调用模型，
  无密钥亦可跑通全流程。
- **示例与文档**：自造示例数据（q3-retention）、Agent Skills 协议入口、
  架构/模型层/路由/工作流/数据可信/许可六份文档、中英 README。
- **验证脚本**：`scripts/verify_deepseek.py`，分级验证 DeepSeek
  OpenAI/Anthropic 双端点（L0 可达性无需密钥）。
- **测试**：42 个测试（路由/线协议/Agent 契约/门禁/版本/集成），无网络依赖。

[0.1.0]: https://github.com/<your-org>/motionnest/releases/tag/v0.1.0
