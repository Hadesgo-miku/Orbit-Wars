"""Orbit Wars 主代码包。

模块组织（详见 master-plan.md §2）：

- src.env       底层环境抽象（M1 物理、M2 几何、M3 世界、M4 安全）
- src.policy    决策层（M5 missions、M6 scoring、M7 value_gbc、M8 modes、M9 plan）
- src.agent     在线推理入口（Kaggle 调用的 ``agent(obs, config)``）
"""
