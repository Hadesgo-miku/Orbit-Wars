# eval/results/ — 评测产出

按 master-plan §5.3 标准格式，每个版本必产两份：

- `v{N}.md`：人类可读 markdown 报告（必看）
- `v{N}.json`：机器可读 JSON（供后续 diff / 趋势图分析）

## 当前已产出

（v0 骨架阶段，尚无评测结果。D2 起 Eval Lead 开始产出。）

## 命名约定

- `v{N}.md` / `v{N}.json`：正式版本评测
- `_raw_v{N}.json`：tournament runner 的原始 raw 输出（由 `report.py` 读）
- `_archive/`：超过 30 天的旧报告归档
