# 模型抽象层设计（docs/model-layer.md）

## 三件套：Provider / Registry / Router

```
agents/*.py                    业务代码（不知道模型的存在）
      │  router.complete(task, messages)
      ▼
llm/router.py   TaskRouter     任务 → 档位 → 模型；降级；人工兜底；审计
      │  registry.provider(name)
      ▼
llm/registry.py ModelRegistry  逻辑名 → ModelSpec → Provider（缓存）
      │  format = openai | anthropic
      ▼
llm/*_provider.py LLMProvider  chat() -> LLMResponse（重试/密钥/健康检查）
```

## 接口格式归一化

| 提供方类型 | 端点拼接 | 认证头 | 响应解析 |
|---|---|---|---|
| OpenAI 兼容 | `{base_url}/chat/completions` | `Authorization: Bearer $KEY` | `choices[0].message.content` |
| Anthropic 兼容 | `{base_url}/v1/messages` | `x-api-key` + `anthropic-version: 2023-06-01` | `content[*].text` 拼接 |

两者的 system 处理不同：OpenAI 是消息角色，Anthropic 是顶层 `system` 字段——
差异全部封装在 Provider 内，对上层不可见。

## 新增一个模型（不改一行代码）

在 `config/models.yaml` 追加：

```yaml
- name: my-model                 # 逻辑名（路由规则引用它）
  model_id: vendor-model-id      # 提供方侧真实 ID
  provider_format: openai        # 或 anthropic
  base_url: https://api.vendor.com
  api_key_env: VENDOR_API_KEY    # 密钥只进环境变量
  tier: low                      # low | strong
  max_output_tokens: 8192
```

然后在 `config/router.yaml` 的某个任务 `candidates` 里引用 `my-model` 即可。

## 档位语义

| 档位 | 定位 | 默认模型 | 任务特征 |
|---|---|---|---|
| `low` | 低成本、高频、可校验 | `deepseek-flash` | 数据解读、分镜、初稿动画、改稿 |
| `strong` | 强推理、审美、终审 | `deepseek-v4-pro` | 配乐审美、复杂三维运镜、成片终审 |

## 调用契约

```python
response = router.complete("storyboard_generation", messages)
# RoutedResponse:
#   text                  模型文本
#   model_used            实际生效的逻辑名
#   tier_used             实际生效的档位
#   degraded              是否未落在首选档位
#   requires_human_signoff 产出是否必须人工签发
#   latency_ms / usage    计量与审计
```

## 安全与可观测

- 密钥只从环境变量读取（`.env` 支持），绝不写入配置或日志；
- 每次调用写入 `audit_trail`（任务/模型/档位/降级/签批要求/耗时），
  `mnest audit` 可查；
- `mnest models check <name>` 对任意模型做真实探测；
- 429/5xx 指数退避重试（默认 3 次），网络错误不会静默吞掉。
