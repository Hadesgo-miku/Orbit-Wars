# Orbit Wars — Replay Dataset (Parquet) - 3,000+ Games Ready to Analyze in Seconds

**Competition:** Orbit Wars

**Topic:** Orbit Wars Replay Dataset (parquet) - 3,000+ games ready to analyze in seconds

**Posted by:** Nicolas Bridelance
**Position in competition:** 1004th
**Posted:** 7 days ago

## Update

Thanks to @chahinovic I've realized that it would be more interesting for everyone if I shared directly my code for dataset building :) so please find it just below:

Dataset building notebook: https://www.kaggle.com/code/nbridelancetb/orbit-wars-build-a-parquet-db-from-raw-replays

Dataset: orbit-wars-replay-parquet

Companion notebook: EDA: Top Player Behavioral Profiles

## TL;DR

I was tired of waiting for my computer to parse gigabytes of JSON replays? So sloooow. So I pre-processed 3,069 episodes from the top-20 leaderboard players into clean Parquet tables. Load in seconds, query instantly with pandas.

## Why Parquet instead of JSON?

Raw JSON replays	This dataset (Parquet)
Size	~15 GB	80 MB (190x smaller)
Load time	Minutes of parsing per game	2 seconds for the full DB
Query	Write a parser, handle edge cases	pd.read_parquet() and go
Filtering	Load everything into memory	Column pruning + row-group filtering
Schema	Nested, inconsistent across versions	Flat, typed, documented

Parquet uses columnar compression — if you only need actions.parquet (fleet launches), you load 17 MB instead of touching 15 GB. And with pyarrow filters, you can load just one player's data without scanning the rest.

## What's in the dataset?

Table	Rows	What it tells you
episodes.parquet	3,069	Game metadata: seed, n_players, winner, angular velocity
player_episodes.parquet	8,114	Who played, who won
tick_summary.parquet	1.99M	Economy curves: ships, production, planets per tick
actions.parquet	2.44M	Every fleet launch: source, angle, ship count
episode_planets.parquet	78K	Map topology: positions, production, orbit radius, static/comet
planet_state.parquet	28.9M	Full ownership + garrison for every planet at every tick

## Quick start

```python
import pandas as pd

# Load the lightweight tables (< 3 seconds total)
episodes = pd.read_parquet("episodes.parquet")
players = pd.read_parquet("player_episodes.parquet")
actions = pd.read_parquet("actions.parquet")
ticks = pd.read_parquet("tick_summary.parquet")

# Win rate leaderboard
wr = players.groupby("name")["is_winner"].mean().sort_values(ascending=False)
print(wr.head(10))

# Economy curves: winner vs loser
curves = ticks.merge(episodes[["episode_id","winner_slot"]], on="episode_id")
curves["is_winner"] = curves["slot"] == curves["winner_slot"]
curves.groupby(["tick","is_winner"])["production"].mean().unstack().plot()

# Load only specific episodes from the big table (row-group filtering)
my_eps = [12345, 12346]
ps = pd.read_parquet("planet_state.parquet", 
                     filters=[("episode_id", "in", my_eps)])
```

## What can you do with this?

- Behavioral profiling: Activity rate, fleet sizes, timing patterns per player
- Strategy research: Reinforcement rates, expansion timing, attack triggers
- Early prediction: Predict winner from tick-50 metrics
- Behavioral cloning: Extract (state, action) pairs for imitation learning
- Board classification: Static-heavy vs rotating-heavy maps

The companion notebook demonstrates all of these with working code and plots.

## How it was built

- Crawled replays from top-20 submissions via the Kaggle Episodes API
- Parsed each JSON into flat, typed columns with pyarrow
- Compressed with appropriate dtypes (int8/int16 where possible) for minimal footprint

If you find interesting patterns or build something on top of this, very interested ;)

## Comments

### 🇵🇸 WakNeo
Posted 2 days ago · 776th in this Competition

The dataset has a packaging bug: episodes.parquet / actions.parquet / player_episodes.parquet cover episode IDs 76.3M–77.2M, but episode_planets.parquet / planet_state.parquet cover 75.6M–76.4M. Only 104 episode IDs appear in all five tables — everything else is missing either the topology or the state.

### 🇵🇸 WakNeo
Posted 2 days ago · 776th in this Competition

The README claims 3,069 episodes have "full state" but in practice only ~3% (104) actually do. The rest are missing either the planet topology + per-tick ownership, OR the actions + metadata + winner labels — meaning you can't reconstruct the game state for them.

```python
import pyarrow.parquet as pq
def ids(f): return set(pq.read_table(f, columns=['episode_id']).to_pydict()['episode_id'])
A = ids('episodes.parquet'); B = ids('planet_state.parquet')
print(f'episodes={len(A)}  planet_state={len(B)}  overlap={len(A & B)}')
# expected: episodes=3069  planet_state=3640  overlap=3069  (or similar)
# actual:   episodes=3069  planet_state=3640  overlap=104
```

### Nicolas Bridelance — Topic Author
Posted a day ago · 1004th in this Competition

Good catch, fixed. Two different scraping batches, non-overlapping ID ranges, stale folder. v2 is live - 4,992 episodes, 100% overlap across all tables:

```python
import pyarrow.parquet as pq
def ids(f): return set(pq.read_table(f, columns=['episode_id']).to_pydict()['episode_id'])
A = ids('episodes.parquet'); B = ids('planet_state.parquet')
print(len(A), len(B), len(A & B))  # 4992 4992 4992
```

While I'm here - the real reason I shared this is to share the idea to stop parsing JSONs to others. I have no doubt that my code for replay conversion from JSON to parquet can be copied and improved :) with little to no effort at all.

Each replay is 5–20 MB of JSON. 3,000 of them = several hours of parsing, every time. Parse once → Parquet, and the same queries run in under a second. If you're doing any serious analysis, a structured DB is a prerequisite, not a nice-to-have.

With this in place I've been running things that weren't feasible before:

- Mission classification: track every fleet from launch to impact, label as EXPAND / SNIPE / RESCUE / WASTE etc. Main finding: winners don't send bigger fleets — they send more of them (3.75/tick late game vs 0.52 for losers).
- Player fingerprinting: behavioral features normalized per-game (cadence, multi-send rate, tempo by phase) → map-independent style signatures. Useful for identifying who you're playing against mid-game.
- Build-order clustering: early-game archetypes from the first 50 ticks — aggressive expander vs economic turtle vs etc. Top players are surprisingly consistent.
- Behavioral cloning: LightGBM trained on (source, target) decisions from Vadasz. Not a strong agent on its own, but useful as a prior for search.

Open question: how are people scaling up bot evaluation?

My current blocker: kaggle_environments runs one game at a time at ~15–30s/game. For any serious tuning loop (evolutionary, RL, grid search) you need thousands of games — that's 8+ hours for 1,000. Not workable.

I have a pure-Python forward simulation that's somewhat faster, but still not fast enough for real scale. What I'd love to know:

- Has anyone written a fast reimplementation of the physics (Cython, Rust, JAX)?
- Is there a clean way to parallelize multiple env instances?
- Would a learned world model (predict next state from current state + actions) be worth building?
- Happy to share the forward sim if there's interest in collaborating on a faster engine.

### hykunnnn
Posted a day ago · 739th in this Competition

I currently have a JAX engine with 1024 environment parallelism, with SPS around 10500. I have already set up a reinforcement learning pipeline. If you are interested, we can discuss cooperation. I see that your data analysis work is excellent.
