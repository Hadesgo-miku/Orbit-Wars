"""M12 — 评测系统。

由 Eval Lead 维护。所有"v3 是否优于 v2"的判断都通过本模块产出的报告做。

模块组织：

- seeds       128 seeds + 32 archetypes 数据（来自社区 ChrisLeiteScha 公开数据）
- tournament  多进程并行对战 runner
- stats       Wilson CI + SPRT 统计工具
- report      markdown 报告生成
- opponents/  本地对手池（L0–L4 5 个等级）
- results/    每个版本的评测产出（v0.md / v0.json 等）
"""
