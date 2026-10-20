#!/usr/bin/env python
"""DeepSeek V4.1 Flash（deepseek-flash）可用性验证脚本。

分级验证策略：
  L0  网络与端点可达性（无需密钥）：TLS 握手 + HTTP 状态码语义
  L1  OpenAI 兼容端点   POST https://api.deepseek.com/chat/completions
  L2  Anthropic 兼容端点 POST https://api.deepseek.com/anthropic/v1/messages

用法：
  python scripts/verify_deepseek.py                     # 全部级别
  python scripts/verify_deepseek.py --model deepseek-flash
  set DEEPSEEK_API_KEY=sk-xxx && python scripts/verify_deepseek.py

退出码：0 = 所有可执行级别通过；1 = 存在失败；2 = 密钥缺失（L0 仍执行）。
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import sys
import time

import httpx

OPENAI_BASE = "https://api.deepseek.com"
ANTHROPIC_BASE = "https://api.deepseek.com/anthropic"
HOST = "api.deepseek.com"


def check_reachability(timeout: float = 10.0) -> tuple[bool, str]:
    """L0：TLS 握手 + 一个无需鉴权的请求，验证端点语义（401 = 可达且鉴权生效）。"""
    try:
        with socket.create_connection((HOST, 443), timeout=timeout):
            pass
    except OSError as exc:
        return False, f"TCP 连接失败：{exc}"
    try:
        context = ssl.create_default_context()
        with socket.create_connection((HOST, 443), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=HOST):
                pass
    except (ssl.SSLError, OSError) as exc:
        return False, f"TLS 握手失败：{exc}"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{OPENAI_BASE}/chat/completions",
                json={"model": "deepseek-flash", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
            )
        if response.status_code in (401, 403):
            return True, f"端点可达，鉴权按预期拦截（HTTP {response.status_code}）"
        return True, f"端点可达（HTTP {response.status_code}，无密钥时的异常语义）"
    except httpx.HTTPError as exc:
        return False, f"HTTP 请求失败：{exc}"


def check_openai_format(api_key: str, model: str, timeout: float = 60.0) -> tuple[bool, str]:
    """L1：OpenAI 兼容端点真实调用。"""
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{OPENAI_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你是 MotionNest 的连通性探针，只回复 ok。"},
                        {"role": "user", "content": "ping"},
                    ],
                    "max_tokens": 16,
                    "temperature": 0,
                },
            )
    except httpx.HTTPError as exc:
        return False, f"请求失败：{exc}"
    latency_ms = int((time.perf_counter() - started) * 1000)
    if response.status_code != 200:
        return False, f"HTTP {response.status_code}：{response.text[:200]}"
    try:
        data = response.json()
        text = (data["choices"][0]["message"]["content"] or "").strip()
        usage = data.get("usage", {})
    except (KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
        return False, f"响应解析失败：{exc}；原始：{response.text[:200]}"
    return True, (
        f"HTTP 200，{latency_ms}ms，回复 {text[:40]!r}，"
        f"tokens in/out={usage.get('prompt_tokens')}/{usage.get('completion_tokens')}"
    )


def check_anthropic_format(api_key: str, model: str, timeout: float = 60.0) -> tuple[bool, str]:
    """L2：Anthropic 兼容端点真实调用。"""
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{ANTHROPIC_BASE}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 16,
                    "temperature": 0,
                    "system": "你是 MotionNest 的连通性探针，只回复 ok。",
                    "messages": [{"role": "user", "content": "ping"}],
                },
            )
    except httpx.HTTPError as exc:
        return False, f"请求失败：{exc}"
    latency_ms = int((time.perf_counter() - started) * 1000)
    if response.status_code != 200:
        return False, f"HTTP {response.status_code}：{response.text[:200]}"
    try:
        data = response.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        usage = data.get("usage", {})
    except (KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
        return False, f"响应解析失败：{exc}；原始：{response.text[:200]}"
    return True, (
        f"HTTP 200，{latency_ms}ms，回复 {text[:40]!r}，"
        f"tokens in/out={usage.get('input_tokens')}/{usage.get('output_tokens')}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepSeek deepseek-flash 可用性验证")
    parser.add_argument("--model", default="deepseek-flash", help="模型 ID（默认 deepseek-flash）")
    parser.add_argument("--skip-network", action="store_true", help="跳过 L0（CI 离线环境用）")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    print(f"== MotionNest · DeepSeek 可用性验证（model={args.model}）==\n")

    exit_code = 0

    if not args.skip_network:
        ok, message = check_reachability()
        print(f"[L0] 端点可达性      : {'PASS' if ok else 'FAIL'}  {message}")
        exit_code |= 0 if ok else 1

    if not api_key:
        print("[L1] OpenAI 格式调用 : SKIP  未设置 DEEPSEEK_API_KEY")
        print("[L2] Anthropic 格式  : SKIP  未设置 DEEPSEEK_API_KEY")
        print("\n提示：export DEEPSEEK_API_KEY=sk-xxx 后重跑，即可完成真实调用验证。")
        return exit_code or 2

    ok, message = check_openai_format(api_key, args.model)
    print(f"[L1] OpenAI 格式调用 : {'PASS' if ok else 'FAIL'}  {message}")
    exit_code |= 0 if ok else 1

    ok, message = check_anthropic_format(api_key, args.model)
    print(f"[L2] Anthropic 格式  : {'PASS' if ok else 'FAIL'}  {message}")
    exit_code |= 0 if ok else 1

    if exit_code == 0:
        print("\n结论：deepseek-flash 双接口格式均可用，可作为 MotionNest 低成本档默认模型。")
    else:
        print("\n结论：存在失败项，请检查网络/密钥/账户额度。")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
