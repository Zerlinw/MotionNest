# MotionNest · 动巢

**English** · [中文](README.md)

<p align="center">
  <strong>Turn a trustworthy dataset into reviewable, revisable, exportable data-story animation.</strong>
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=flat-square">
  <a href="CHANGELOG.md"><img alt="Version 0.3.0" src="https://img.shields.io/badge/version-0.3.0-blueviolet.svg?style=flat-square"></a>
  <a href="tests"><img alt="Tests: 106 passed" src="https://img.shields.io/badge/tests-106%20passed-brightgreen.svg?style=flat-square"></a>
  <img alt="Platform: Windows / macOS / Linux" src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg?style=flat-square">
  <a href="CONTRIBUTING.md"><img alt="PRs welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square"></a>
</p>

> Models propose. Deterministic programs compute. Humans approve.
> Every moving frame traces back to a number, a piece of evidence, and a version.

MotionNest is an **agent-driven animation workbench**: feed it structured data (CSV/JSON)
plus a data dictionary, and agents handle data interpretation, narrative planning,
storyboarding, draft animation and targeted revision; music aesthetics, complex 3D camera
work and final review run on a strong model tier with a mandatory human sign-off and a
human fallback queue; a local render pipeline produces the MP4, subtitles and citation list.

**It is not a text-to-video tool** — traceable numbers, locatable comments, rollback-able
edits and reproducible versions are what set it apart from "one-prompt slot-machine output".

---

## Table of Contents

- [Core Features](#core-features)
- [Architecture Overview](#architecture-overview)
- [Model Tiers and Task Routing](#model-tiers-and-task-routing)
- [Quick Start](#quick-start)
- [Desktop Tool (exe)](#desktop-tool-exe)
- [Configuration Examples](#configuration-examples)
- [CLI Reference](#cli-reference)
- [Project Structure](#project-structure)
- [Four Quality Gates](#four-quality-gates)
- [Development and Testing](#development-and-testing)
- [Roadmap](#roadmap)
- [Compliance and Licensing](#compliance-and-licensing)

---

## Core Features

- **Pluggable model layer**: Provider / Registry / Router abstraction, compatible with
  **OpenAI and Anthropic wire formats** out of the box. Adding a model = editing YAML only;
  business code never changes.
- **Two tiers, explicit division of labor**: the low-cost tier `deepseek-flash`
  (DeepSeek V4.1 Flash) handles data interpretation, storyboard generation, draft animation
  and animation revision; the strong tier `deepseek-v4-pro` handles music aesthetics,
  complex 3D camera design and final review — its output always requires human sign-off.
- **Human fallback as a mechanism**: when the strong tier is unavailable, the low tier
  produces a draft flagged `degraded + requires_human_signoff`; when both are unavailable,
  the task enters `reviews/human-queue.json`. The release gate blocks any unsigned artifact.
- **Data trust**: data snapshots, dictionaries, metric definitions and sources are
  first-class citizens; evidence IDs chain screen elements → shot assertions →
  metric definitions → raw data rows.
- **Frame-level review and revision**: the scene tree is the single source of truth and
  layers carry stable IDs; comments capture time point and coordinates, hit-testing locates
  the layer, and targeted patches only touch the target properties — unrelated scenes are
  never rebuilt.
- **Rollback-able versions**: every approval produces a content-addressed snapshot;
  `mnest undo` restores the entire project state; exports embed an audit manifest
  (data source, gate results, sign-offs, version).
- **Local rendering**: Composition JSON → HTML scenes → (optional Playwright frame capture)
  → FFmpeg MP4; missing render dependencies degrade gracefully to HTML + manifest without
  blocking the workflow.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│ Agent orchestration layer (src/motionnest/agents/)            │
│  DataInterpreter · StoryboardAgent · Animator · Reviser       │
│  MusicDirector · CameraDesigner · FinalReviewer               │
│  Only ever calls TaskRouter.complete(task, messages)          │
├──────────────────────────────────────────────────────────────┤
│ Model abstraction layer (src/motionnest/llm/)                 │
│  TaskRouter ──► ModelRegistry ──► LLMProvider                 │
│                                  ├── OpenAIProvider           │
│                                  └── AnthropicProvider        │
│  Rules: config/router.yaml + config/models.yaml               │
├──────────────────────────────────────────────────────────────┤
│ Deterministic layer (core/ data/ composition/ qa/)             │
│  Project state & versions · data snapshots/gates ·            │
│  timeline/scene tree · four quality gates                     │
├──────────────────────────────────────────────────────────────┤
│ Presentation layer (runtime/ studio/ cli/)                     │
│  HTML scenes · frame capture · FFmpeg muxing ·                │
│  comment inbox · mnest CLI                                    │
└──────────────────────────────────────────────────────────────┘
```

See [docs/architecture.md](docs/architecture.md) for module responsibilities and
[docs/model-layer.md](docs/model-layer.md) for the model abstraction design.

## Model Tiers and Task Routing

| Task | Tier | Default model | Human sign-off | Description |
|---|---|---|---|---|
| `data_interpretation` | low | `deepseek-flash` | No | Field understanding, metric summary, narrative candidates |
| `storyboard_generation` | low | `deepseek-flash` | No | Per-shot timecodes + data assertions + evidence binding |
| `draft_animation` | low | `deepseek-flash` | No | Scene tree, layers, animation primitives |
| `animation_revision` | low | `deepseek-flash` | No | Comment → targeted patch |
| `music_aesthetics` | strong | `deepseek-v4-pro` | **Yes** | The model has no hearing: beat/energy structure only |
| `camera_3d_design` | strong | `deepseek-v4-pro` | **Yes** | Simple moves use deterministic templates; complex moves use the strong model |
| `final_review` | strong | `deepseek-v4-pro` | **Yes** | Numeric consistency, disclosure, rhythm review |

Full routing rules: [docs/task-routing.md](docs/task-routing.md).

## Quick Start

### 1. Install

```bash
git clone https://github.com/<your-org>/motionnest.git
cd motionnest

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # add [render] for frame-by-frame rendering
```

Requirements: Python ≥ 3.10; optional FFmpeg (video encoding); optional Playwright +
Chromium (frame capture).

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env and fill in your DeepSeek API key (apply at https://platform.deepseek.com)
#   DEEPSEEK_API_KEY=sk-xxx
```

### 3. Environment and model self-check

```bash
mnest doctor                      # Python/FFmpeg/Playwright/config/keys
mnest models list                 # registered models and tiers
mnest models check deepseek-flash # live probe (consumes a tiny amount of quota)
python scripts/verify_deepseek.py # graded verification of both DeepSeek wire formats
```

### 4. Run the example (offline mode, no key required)

```bash
mnest new q3-story --path examples/q3-retention
mnest data add examples/q3-retention/data/q3.csv \
  --project examples/q3-retention/q3-story \
  --dictionary examples/q3-retention/data/dictionary.json
mnest plan  --project examples/q3-retention/q3-story --offline --approve cand-1
mnest compose --project examples/q3-retention/q3-story --offline --duration 24000
mnest render  --project examples/q3-retention/q3-story
```

Once a key is configured, drop `--offline` to switch to the low-cost model pipeline.

## Desktop Tool (exe)

The quick-start flow is also available as an **IntelliJ IDEA-style desktop app**: Darcula /
IntelliJ Light themes with one-click switching, configurable parameters (API keys, endpoints,
model IDs) and variable parameters (prompts, conversations) editable in the UI and persisted.

```bash
# Development mode
pip install -e ".[desktop]"
python -m desktop                 # launch GUI
python -m desktop --selfcheck     # headless self-check

# Package into a dependency-free exe (double-click to run, ~55 MB)
pip install pyinstaller PySide6
python scripts/build_exe.py       # produces dist/MotionNestDesktop.exe
```

| Page | Contents |
|---|---|
| Quick Start | Seven-step wizard: doctor → create project → import data → interpret & approve → storyboard & draft → music & camera → review, render & export |
| Settings | Configurable parameters: keys (password fields), endpoints, model IDs, timeout/retries, human-fallback toggle |
| Prompt | Variable parameters: system prompts and user-prompt templates for all seven tasks, applied on save |
| Chat | Variable parameters: pick a model, edit the system prompt, multi-turn chat (tier/latency/tokens shown) |

The exe runs in green mode: settings live next to it in `motionnest-settings.json`, and
`config/` ships inside the bundle. See [docs/desktop.md](docs/desktop.md).

## Configuration Examples

### Model registry (`config/models.yaml`, excerpt)

```yaml
models:
  - name: deepseek-flash            # logical name referenced by routing rules
    model_id: deepseek-flash        # DeepSeek V4.1 Flash
    provider_format: openai         # OpenAI-compatible endpoint
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY
    tier: low
    max_output_tokens: 8192

  - name: deepseek-v4-pro
    model_id: deepseek-v4-pro
    provider_format: openai
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY
    tier: strong
```

### Same model, Anthropic wire format

```yaml
  - name: deepseek-flash-anthropic
    model_id: deepseek-flash
    provider_format: anthropic      # auto-appends /v1/messages
    base_url: https://api.deepseek.com/anthropic
    api_key_env: DEEPSEEK_API_KEY
    tier: low
```

### Task routing (`config/router.yaml`, excerpt)

```yaml
routes:
  storyboard_generation:            # low tier: preferred → strong fallback → hard fail
    preferred_tier: low
    candidates: [deepseek-flash]
    fallback_tiers: [strong]
    human_review: false

  music_aesthetics:                 # strong tier: low-tier draft + sign-off; none → human queue
    preferred_tier: strong
    candidates: [deepseek-v4-pro]
    fallback_tiers: [low]
    human_review: true
```

## CLI Reference

| Command | Purpose |
|---|---|
| `mnest doctor` | Environment check (Python/FFmpeg/Playwright/config/keys) |
| `mnest models list\|check\|routes` | Model list / live probe / routing table |
| `mnest new <name>` | Create a project workspace |
| `mnest data add\|verify` | Data import (passes the data gate) / re-run the gate |
| `mnest plan [--approve ID] [--offline]` | Data interpretation → narrative candidates → human approval |
| `mnest compose [--offline]` | Storyboard + draft animation scene tree |
| `mnest revise "comment" --scene --layer` | Targeted revision (auto-detects data-layer changes) |
| `mnest music\|camera` | Music planning / 3D camera design (strong tier) |
| `mnest review report\|approve` | Final review / human sign-off |
| `mnest render [--quality preview\|final]` | HTML scenes → (optional frame capture) → MP4 |
| `mnest export` | Four gates + three sign-offs → final cut + audit manifest |
| `mnest inbox post\|list\|next\|done` | Comment inbox (point at the frame to change it) |
| `mnest undo\|audit` | Roll back to the previous snapshot / version & call audit |

## Project Structure

```
motionnest/
├── README.md / README.en.md      # Project docs (Chinese / English)
├── LICENSE / THIRD_PARTY.md      # MIT; third-party asset licensing
├── CONTRIBUTING.md / SECURITY.md / CHANGELOG.md
├── pyproject.toml                # Packaging, dependencies, CLI entry point mnest
├── config/
│   ├── models.yaml               # Model registry (logical name/ID/format/endpoint/key/tier)
│   └── router.yaml               # Task routing rules (tier/candidates/fallback/sign-off)
├── src/motionnest/
│   ├── cli.py                    # mnest commands: workflow orchestration
│   ├── settings.py               # Config discovery and Registry/Router construction
│   ├── llm/                      # Model abstraction layer
│   │   ├── base.py               #   LLMProvider abstraction (retry/keys/health check)
│   │   ├── openai_provider.py    #   OpenAI-compatible (/chat/completions)
│   │   ├── anthropic_provider.py #   Anthropic-compatible (/v1/messages)
│   │   ├── registry.py           #   ModelSpec + Provider factory/cache
│   │   └── router.py             #   TaskRouter: tier decisions/degradation/human fallback/audit
│   ├── agents/                   # Agent business layer (depends on TaskRouter only)
│   │   ├── prompts.py            #   Prompt store (overridable, editable from desktop)
│   │   ├── data_interpreter.py   #   Data interpretation (low)
│   │   ├── storyboard.py         #   Storyboard generation (low)
│   │   ├── animator.py           #   Draft animation (low)
│   │   ├── reviser.py            #   Animation revision (low)
│   │   ├── music_director.py     #   Music aesthetics (strong + human)
│   │   ├── camera_designer.py    #   3D camera design (strong + human; simple → template)
│   │   └── final_reviewer.py     #   Final review (strong + human)
│   ├── core/                     # Project state / version snapshots / full-chain schemas
│   ├── data/                     # Loading / summaries / data dictionary / data gate
│   ├── composition/              # Timeline / scene tree / targeted patches
│   ├── runtime/                  # HTML scenes / frame capture / FFmpeg
│   ├── studio/                   # Comment inbox / coordinate hit-testing
│   └── qa/                       # Four quality gates
├── desktop/                      # Desktop tool (PySide6, IDEA dual themes)
│   ├── app.py                    #   Main window: toolbar/tool window/page stack/console
│   ├── theme.py                  #   Darcula / IntelliJ Light palettes and QSS
│   ├── bridge.py                 #   Desktop → motionnest operation wrappers
│   ├── settings.py               #   Configurable parameter persistence (green/APPDATA)
│   ├── workers.py                #   Background threads
│   ├── console.py                #   Run-tool-window style console
│   └── pages/                    #   Quick start / settings / prompt / chat
├── skills/motionnest/            # Agent Skills protocol entry (SKILL.md + methodology docs)
├── templates/                    # Starter templates (constraints only, no numbers)
├── examples/q3-retention/        # Synthetic example data + one-command walkthrough
├── docs/                         # Architecture / model layer / routing / workflow / data trust / licensing
├── scripts/verify_deepseek.py    # Graded verification of both DeepSeek wire formats
└── tests/                        # Unit + integration (MockTransport/StubProvider, no network)
```

## Four Quality Gates

| Gate | Checks | Blocking point |
|---|---|---|
| Data gate | Dictionary coverage, required-field nulls, units, source, timezone | Before generation |
| Logic gate | Evidence binding, recomputability, declared ignored information | Before compose |
| Visual gate | Unique layer IDs, text length, chart structure | After compose |
| Release gate | All three human sign-offs present (music / camera / final review) | Before export |

No gate failure may auto-export a release build — gates emit actionable errors, not vague warnings.

## Development and Testing

```bash
pip install -e ".[dev]"
pytest                       # full suite: routing/wire protocol/agent contracts/gates/integration/desktop bridge
ruff check src tests         # lint
```

Tests are network-free: provider wire protocols use `httpx.MockTransport`, model calls use
`StubProvider`, covering URLs, headers, payloads and response parsing for both the OpenAI
and Anthropic formats.

## Roadmap

- [x] Model abstraction layer: dual wire formats + tier routing + human fallback + audit
- [x] Low-tier tasks: data interpretation / storyboard / draft animation / revision
- [x] Strong-tier tasks + human sign-off + release gate
- [x] Offline template pipeline (keyless walkthrough) + example data
- [ ] Playwright frame capture for multiple aspect ratios (16:9 / 9:16 / 1:1)
- [ ] Studio browser editor (playback / click-select / drag values / comments)
- [ ] TTS narration and subtitle tracks, user-licensed music ingestion
- [ ] API/database connectors and collaborative comments

## Compliance and Licensing

Source code is MIT (see [LICENSE](LICENSE)). MIT does **not** cover user-uploaded data,
fonts, images, audio, logos or trademarks, nor third-party dependencies or model-provider
terms of service (see [THIRD_PARTY.md](THIRD_PARTY.md)).

This project borrows publicly describable workflow methodology only (artifact decomposition,
rule-based constraints, plan-before-render, targeted revision, version sedimentation). It does
not copy code, assets, characters, copy or private formats from any third-party project. For
high-risk domains such as finance, healthcare, law and public policy, it provides visualization
and narrative assistance only and is not a substitute for professional advice.
