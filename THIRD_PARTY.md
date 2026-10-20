# 第三方资产与许可清单（THIRD_PARTY.md）

MIT 许可仅覆盖 MotionNest 自身的源代码与文档，**不自动覆盖**任何第三方资产。
新增依赖或素材前，必须在本文件登记并完成许可确认。

## 运行时依赖

| 名称 | 版本约束 | 许可证（SPDX） | 用途 |
|---|---|---|---|
| httpx | >=0.27,<1.0 | BSD-3-Clause | HTTP 客户端（模型调用、连通性检查） |
| pydantic | >=2.7,<3.0 | MIT | 数据模型与 schema 校验 |
| PyYAML | >=6.0,<7.0 | MIT | 配置文件解析 |
| typer | >=0.12,<1.0 | MIT | CLI 框架 |
| rich | >=13.7,<14.0 | MIT | 终端输出 |
| python-dotenv | >=1.0,<2.0 | BSD-3-Clause | `.env` 加载 |

## 可选依赖（默认不安装）

| 名称 | 版本约束 | 许可证（SPDX） | 用途 |
|---|---|---|---|
| playwright | >=1.40 | Apache-2.0 | 无头浏览器截帧渲染（需另行接受其捆绑浏览器许可） |

## 外部服务

| 服务 | 端点 | 说明 |
|---|---|---|
| DeepSeek API | https://api.deepseek.com（OpenAI 兼容）<br>https://api.deepseek.com/anthropic（Anthropic 兼容） | 默认模型提供方，使用条款见其官网 |
| OpenAI API | https://api.openai.com/v1 | 可选启用 |
| Anthropic API | https://api.anthropic.com | 可选启用 |

## 素材边界

- 用户上传的数据、字体、图像、音频、视频、Logo 与商标，遵循各自许可，与本项目 MIT 无关。
- 模板、示例数据与示例乐谱如无另行声明，均为项目自造，可随 MIT 使用。
- 音乐、配音、字体、肖像与 AI 生成内容用于商业发布前，须另行取得授权。
- 项目不提供任何版权或商标担保；无法确认许可的资产不得进入正式导出（发布门禁会拦截）。
