# 桌面工具（docs/desktop.md）

MotionNest Desktop 把 README「快速开始」流程封装为 **IntelliJ IDEA 风格的桌面应用**：
Darcula / IntelliJ Light 双主题、可配置参数面板、可变参数（Prompt / 对话）编辑、
底部 Run 风格控制台。打包后的 exe **双击即运行，无需 Python 环境**。

## 运行方式

```bash
# 开发模式（需 Python 3.10+ 与 PySide6）
pip install -e ".[desktop]"
python -m desktop

# 无头自检（CI / 排障）：离屏初始化 + 构建模型栈 + 验证双主题
python -m desktop --selfcheck --demo
```

## 打包为 exe

```bash
pip install pyinstaller PySide6
python scripts/build_exe.py            # 产出 dist/MotionNestDesktop.exe（onefile + windowed）
python scripts/build_exe.py --console  # 附带控制台版（自检/调试）
python scripts/build_exe.py --clean    # 清理构建目录
```

构建产物（约 55 MB，onefile）：

```
dist/
├── MotionNestDesktop.exe          # 双击运行
├── motionnest-settings.json       # 首次运行自动生成（绿色模式：设置存于 exe 同级）
└── motionnest-selfcheck.txt       # --selfcheck 的报告
```

> `config/models.yaml` 与 `config/router.yaml` 随包分发；换模型改 YAML 后需重新打包，
> 或直接在「设置」页覆盖服务地址 / 模型 ID / 密钥（无需重新打包）。

## 界面布局（对齐 IntelliJ IDEA）

```
┌───────────────────────────────────────────────────────────┐
│ MotionNest Desktop   模型可插拔 · 双档位路由 · 帧帧可审      │  顶栏
│                          [Darcula] [IntelliJ Light] [控制台]│
├──────────┬────────────────────────────────────────────────┤
│ 快速开始  │                                                │
│ 设置      │              页面堆叠区                          │  工具窗
│ Prompt   │                                                │
│ 对话      │                                                │
├──────────┴────────────────────────────────────────────────┤
│ 运行 │ [00:12:34] INFO 数据门禁通过：8 行 × 5 列            │  控制台
└───────────────────────────────────────────────────────────┘
```

配色规范：Darcula 面板 `#3C3F41` / 编辑器 `#2B2B2B` / 强调蓝 `#4A88C7`；
Light 面板 `#F2F2F2` / 编辑器 `#FFFFFF` / 强调蓝 `#3574F0`；
1px 细边框、4px 圆角、紧凑间距、蓝色焦点与选中态（`desktop/theme.py`）。

## 布局与响应式

| 指标 | 取值 | 说明 |
|---|---|---|
| 默认窗口 | 1480 × 920 | 常见笔记本/台式机一屏完整显示 |
| 最小窗口 | 1240 × 760 | 低于此尺寸前内容不挤压变形 |
| 侧栏宽度 | 264 px | 导航项 13.5px 字号、选中项蓝色左条纹 |
| 控件规格 | 输入/按钮/下拉 最小高度 30px，圆角 4px | 框体可读可点 |
| 表格行高 | 44px | 设置页模型表格；列宽策略：只读列内容自适应、可编辑列按权重拉伸 |
| 表单间距 | 行距 12–16px | 统一标签右对齐、字段扩展填充 |

响应式策略：快速开始页与设置页均带滚动区——窗口小于内容时出现滚动条而非截断；
1280×800 下所有页面内容完整可达（已截图验证双主题）。

## 两类参数

### 可配置参数（设置页，持久化）

| 参数 | 说明 |
|---|---|
| API Key | 按 `api_key_env` 输入（密码框），仅存本机设置文件 |
| 服务地址 | 覆盖 `base_url`（默认取自 `config/models.yaml`） |
| 模型 ID | 覆盖 `model_id` |
| 请求超时 / 重试次数 | Provider 层行为 |
| 允许人工兜底 | 强模型不可用时是否转人工队列 |
| 配置目录 | 自定义 models.yaml / router.yaml 位置 |

保存即生效：写入环境变量 + 重建注册表，无需重启。设置文件位置：
`MNEST_DESKTOP_SETTINGS` 环境变量 > exe 同级 `motionnest-settings.json`（绿色模式）>
`%APPDATA%/MotionNest/settings.json`。

### 可变参数（Prompt 页 / 对话页）

- **Prompt 页**：七个任务的系统提示词与用户提示词模板（`$name` 占位符），
  编辑后「保存覆盖」立即生效，可随时恢复默认；
- **对话页**：选择模型、编辑系统提示词、多轮对话，显示模型 / 档位 / 延迟 / token 用量。

## 七步向导（对应 README 快速开始）

1. **环境自检**：Python / FFmpeg / Playwright / 各模型密钥；
2. **创建项目**：项目名 + 父目录 + 模板；
3. **导入数据**：CSV/JSON + 数据字典，跑数据门禁；
4. **数据解读与批准**：填写 brief → 生成叙事候选 → 批准一个；
5. **分镜与初稿动画**：时长 / 帧率 / 分辨率，可勾选离线模板；
6. **配乐与运镜**：强模型档任务，产出需人工签批，模型不可用时自动转人工兜底队列；
7. **终审、渲染与导出**：终审报告 → 全部签批 → 渲染 → 导出（四道门禁把关）。

## 自检与排障

```bash
# 离屏自检（会写报告到 exe 同级或临时目录）
MotionNestDesktop.exe --selfcheck --demo
```

自检覆盖：设置加载、主窗口构建、双主题 QSS、模型栈构建、主题切换。
任一项 FAIL 时，报告文件会指出具体原因（缺配置 / 缺密钥 / 缺依赖）。
