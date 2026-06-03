# tests/ — 单元测试

## 原则

- 每个 Task agent 实现完模块后，必须**同步补**对应的 `test_{module}.py`
- 测试要快：单文件 `pytest` 应在 5 秒内完成（不跑 env.run）
- 性能测试单独放 `perf_{module}.py`（用 ``pytest -m perf`` 跑）

## 命名约定

| 测试目标 | 文件 |
|------|------|
| `src/env/physics.py` | `tests/test_physics.py` |
| `src/env/geometry.py` | `tests/test_geometry.py` |
| `src/env/world.py` | `tests/test_world.py` |
| `src/env/safety.py` | `tests/test_safety.py` |
| `src/policy/missions/*.py` | `tests/test_missions_{name}.py` |
| `src/policy/scoring.py` | `tests/test_scoring.py` |
| `src/policy/modes.py` | `tests/test_modes.py` |
| `src/policy/value_gbc.py` | `tests/test_value_gbc.py` |
| `src/policy/plan.py` | `tests/test_plan.py` |
| `src/agent.py` | `tests/test_agent.py` |
| 评测系统 | `tests/test_eval_stats.py` 等 |

## 跑测试

```bash
# 全部
pytest tests/ -v

# 单文件
pytest tests/test_physics.py -v

# 性能测试
pytest tests/ -m perf -v
```

## 当前状态（v0）

仅 `test_physics.py`（M1 已实现，可跑通）和 `test_stats.py`（M12 的 Wilson CI 已实现）。
其他模块为 NotImplementedError，对应测试会被 ``pytest.skip``，待 Task agent 实现时一并添加。
