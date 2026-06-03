# reports/ — Replay 分析报告

由 Replay Analyst 维护。

## 文件类型

- `week{N}-replay-analysis.md`：每周必产周报
- `submission-v{N}-diagnosis.md`：每次提交的败局诊断

## 周报模板（必含）

```markdown
# Week {N} Replay Analysis (YYYY-MM-DD ~ YYYY-MM-DD)

## 总览
- 本周提交版本：v{X}, v{Y}
- 本周对手分布（Top 10）

## 输给谁
| Opponent ID | Submitter | 胜率 | 局数 | Δ vs 上周 |
|---|---|---|---|---|
| ... |

## 输在哪儿（mission classification）
- EXPAND 阶段：x%
- SNIPE 阶段：x%
- RESCUE 阶段：x%
- WASTE 比例：x%

## 输在哪类地图（archetype 分布）
- ...

## 下周一件事
**具体可执行**的改进建议。
```
