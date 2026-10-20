"""MotionNest（动巢）：文档进、30 秒企业设备宣传片出。

设计主线：
- 输入极简：Markdown / CSV / PPTX 文档 + 素材文件夹，无需向导式配置；
- 蒸馏分层：LLM 把文档蒸馏成要点简报与固定骨架分镜，失败自动降级模板；
- 时长确定：分镜总时长硬约束 30000ms，逐帧渲染后用 ffprobe 复核；
- 本机出片：Composition → HTML 场景 → Playwright 逐帧 → FFmpeg MP4。
"""

__version__ = "0.3.0"
