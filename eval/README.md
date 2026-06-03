# eval/ — 评测系统（M12）

Owner: **Eval Lead**

## 设计原则

> **本地评测是一切决策的基础。** 详见 [`../master-plan.md`](../master-plan.md) §5。

## 模块对应

| 文件 | 职责 |
|------|------|
| `seeds.py` | 128 seeds + 32 archetypes（已落盘，无需修改） |
| `tournament.py` | 多进程并行 runner |
| `stats.py` | Wilson CI + SPRT（已落盘，已实现） |
| `report.py` | markdown 报告生成 |
| `opponents/` | 5 个等级的本地对手 |
| `results/` | 每个版本评测产出（v0.md / v0.json …） |

## 对手池（来自 master-plan §5.2）

| 等级 | 文件 | 目标胜率 | 状态 |
|------|------|------|------|
| L0 | `random_agent.py` | 100% | ✅ 已实现 |
| L1 | `nearest_sniper.py` | 90%+ | ✅ 已实现 |
| L2 | `may18_launch_safety.py` | 70%+ | 🚧 待 Task agent 移植 |
| L3 | `public_heuristic_1110.py` | 55%+ | 🚧 待 Task agent 移植 |
| L4 | `lb_1200_baseline.py` | 50%+ | 🚧 待 Task agent 移植 |

## 评测报告标准格式

见 [`../master-plan.md`](../master-plan.md) §5.3 的完整模板。

放在 `eval/results/v{N}.md`（必产）+ `eval/results/v{N}.json`（机器可读，必产）。

## 跑一次评测

```bash
# 快速（32 seeds × L1 = 32 局，~30s）
python -m eval.tournament --agent src/agent.py --opponents nearest_sniper --seeds 16

# 完整（128 seeds × L1-L4 = 1024 局，~10 分钟）
python -m eval.tournament --agent src/agent.py --opponents all --seeds 128

# 生成报告
python -m eval.report --raw eval/results/_raw_v1.json --version v1 \
    --prev eval/results/_raw_v0.json --output eval/results/v1.md
```
