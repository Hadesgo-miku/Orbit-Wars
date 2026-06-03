# data/ — 数据缓存

**本目录内容不进 git**（见根目录 `.gitignore`）。

## 子目录

| 目录 | 内容 | 大小预估 |
|------|------|------|
| `replays/` | Kaggle Episodes API 拉取的 replay JSON | 每局 5–20MB |
| `parquet/` | 自建或社区的 parquet 数据集 | 80MB（4992 局） |
| `episodes/` | submission_id 对应的 episode list CSV | < 1MB |

## 推荐数据来源

1. **官方日更 replay 索引**：`bovard/orbit-wars-episodes-index`
2. **社区 Parquet 数据集**（强烈推荐用这个）：
   ```bash
   kaggle datasets download nbridelancetb/orbit-wars-replay-parquet --unzip
   ```
3. **每日 top-10% replay**：`bovard/orbit-wars-top10-episodes-{date}`（注意 4P 文件不全）

## 拉取自己 submission 的 replay

```bash
python -m tuning.replay_analyzer download \
    --submission_id 12345678 \
    --output_dir data/replays/
```
