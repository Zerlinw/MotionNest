# 贡献指南（CONTRIBUTING.md）

感谢参与 MotionNest。提交前请阅读以下约定。

## 开发环境

```bash
git clone <your-fork> && cd motionnest
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
ruff check src tests
```

## 提交 PR 的最低要求

1. **测试**：新功能必须带测试；模型层改动必须覆盖双接口格式
   （`httpx.MockTransport`），不引入真实网络依赖。
2. **不破坏隔离**：业务代码（`agents/`）不得 import 任何 Provider；
   模型输出必须先过 Pydantic schema 才能进入执行区。
3. **门禁语义**：不得为了"跑通"而放宽数据门/逻辑门/视觉门/发布门。
4. **数据与素材**：不接受真实个人信息、客户数据、受版权素材或未授权内容；
   示例数据必须自造。
5. **许可**：新增依赖登记到 `THIRD_PARTY.md`（名称/版本/SPDX/用途）。

## 提交信息

 Conventional Commits：`feat:` / `fix:` / `docs:` / `test:` / `refactor:` / `chore:`。

## 行为准则

对事不对人；评审聚焦正确性、可追溯性与可测试性。发现安全问题请见
[SECURITY.md](SECURITY.md) 的私下披露流程，不要开公开 issue。
