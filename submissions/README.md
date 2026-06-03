# submissions/ — 提交记录

| 文件 | 用途 |
|------|------|
| `log.md` | 每次提交的版本号 / commit message / 24h 后 ELO（**Orchestrator 维护**） |
| `packages/` | 打包后的 `main.py` 或 `*.tar.gz`（**不进 git**，每次重新生成） |

## 提交打包

```bash
python -m submissions.pack --version v1
# 输出 submissions/packages/v1.tar.gz
kaggle competitions submit orbit-wars \
    -f submissions/packages/v1.tar.gz \
    -m "v1: launch-safety + commitment + cma-es round 1"
```

## 提交后

按 master-plan §5.5 拉 replay + 诊断：

```bash
python -m tuning.replay_analyzer download --submission_id <ID> --losses-only
python -m tuning.replay_analyzer diagnose --submission_id <ID> \
    --output reports/submission-v1-diagnosis.md
```
