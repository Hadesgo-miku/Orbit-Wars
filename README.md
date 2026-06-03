# Orbit Wars — Kaggle 竞赛工作仓

> **🚀 第一次进入本仓的 agent 请先读 [`master-plan.md`](master-plan.md)。** 那是仓库的唯一权威文档。本 README 仅做快速导航。

## 一句话定位

固定走 **Heuristic 主线**（Mission Family 重构 + CMA-ES 调参 + GBC 价值函数 tie-break + 严密的离线评测闭环），目标：6/22 final submission 进入 silver 区（≥1150），力争摸到 gold 下沿（≥1300）。

## 目录速览

| 目录 | 内容 | 主要 owner |
|------|------|------|
| `master-plan.md` | **必读** 主路线与协作总纲 | Orchestrator |
| `guidance.md` | 总体工作指引（最小必读清单） | — |
| `orbit-wars-overview.md` | 竞赛规则原文 | — |
| `orbit-wars-guide/` | 环境机制 + 提交流程 | — |
| `community-discussions/` | 社区讨论备份 | — |
| `community-examples/` | 公开 notebook 备份 | — |
| `src/` | 主代码（agent / policy / env） | Code Lead + Task agents |
| `eval/` | 评测系统 + 对手池 + 结果 | Eval Lead |
| `tuning/` | CMA-ES + GBC 训练 + replay 分析 | Task agents + Replay Analyst |
| `tests/` | 单元测试 | 每个 Task agent 补充 |
| `data/` | replay JSON / parquet / episode CSV（**不进 git**） | Replay Analyst |
| `reports/` | 周报 + 败局诊断 | Replay Analyst |
| `submissions/` | 提交记录 + 打包后的 `.tar.gz` | Orchestrator |

## 当前版本

**v0：仓库骨架完成**（2026-06-03）

接下来按 `master-plan.md` §4.2 的 P0 任务清单进入 D2–D3 工作（评测系统 + 数据管线）。

## 环境准备

```bash
pip install -r requirements.txt
```

注意：**必须使用 `kaggle-environments >= 1.29.1`**，否则 sweep 物理与线上不一致（见 `community-discussions/sweep-logic-visualizer-updates-pinned.md`）。

## 常用 Shell 速查

```bash
# 跑一次默认对手套餐评测（256 局 ≈ 3 分钟）
python -m eval.tournament --agent src/agent.py --opponents all --seeds 32

# 生成 markdown 评测报告
python -m eval.report --version v1 > eval/results/v1.md

# CMA-ES 调参（一次性，CPU 即可）
python -m tuning.cma_es --params tuning/configs/v1_params.json \
    --budget 1500 --output tuning/best_params_v1.json

# 训 GBC 价值函数
python -m tuning.train_gbc --replays data/replays/ \
    --output src/policy/value_gbc_trees.py

# 打包并提交
python -m submissions.pack --version v1
kaggle competitions submit orbit-wars -f submissions/packages/v1.tar.gz \
    -m "v1: launch-safety + commitment + cma-es round 1"
```
