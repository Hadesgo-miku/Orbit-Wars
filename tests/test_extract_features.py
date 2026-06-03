"""extract_features schema 单元测试。"""
from __future__ import annotations

from tuning.replay_scraper.extract_features import (
    ALL_COLUMNS,
    FEATURE_NAMES,
    META_COLUMNS,
    build_state_features,
    extract_from_replay,
    ExtractConfig,
)


def _minimal_replay() -> dict:
    """最小 mock replay：一步出舰 + 一步 idle。"""
    planet = [0, 0, 20.0, 50.0, 3.0, 30, 2]
    target = [1, 1, 80.0, 50.0, 4.0, 5, 1]
    obs = {
        "player": 0,
        "step": 1,
        "angular_velocity": 0.0,
        "planets": [planet, target],
        "fleets": [],
    }
    ang = 0.0
    return {
        "rewards": [1, -1],
        "steps": [
            [{"observation": obs, "action": [], "status": "ACTIVE"}],
            [
                {
                    "observation": obs,
                    "action": [[0, ang, 10]],
                    "status": "ACTIVE",
                    "reward": 0,
                },
                {
                    "observation": {**obs, "player": 1},
                    "action": [],
                    "status": "ACTIVE",
                    "reward": 0,
                },
            ],
        ],
    }


def test_feature_names_count_and_prefixes():
    assert len(FEATURE_NAMES) == 47
    assert len([f for f in FEATURE_NAMES if f.startswith("g_")]) == 20
    assert len([f for f in FEATURE_NAMES if f.startswith("s_")]) == 10
    assert len([f for f in FEATURE_NAMES if f.startswith("t_")]) == 12
    assert len([f for f in FEATURE_NAMES if f.startswith("c_")]) == 5


def test_build_state_features_idle_zeros_source_target():
    obs = {
        "player": 0,
        "step": 10,
        "angular_velocity": 0.0,
        "planets": [[0, 0, 30.0, 50.0, 2.0, 10, 1]],
        "fleets": [],
    }
    feats = build_state_features(obs, -1, -1, 2)
    for name in FEATURE_NAMES:
        assert name in feats
        if name.startswith("s_") or name.startswith("t_"):
            assert feats[name] == 0.0


def test_extract_from_replay_schema():
    cfg = ExtractConfig(idle_keep_rate=1.0)
    rows = extract_from_replay(_minimal_replay(), episode_id=99, config=cfg, rng_seed=0)
    assert rows
    for row in rows:
        for col in ALL_COLUMNS:
            assert col in row
        assert len([k for k in row if k in FEATURE_NAMES]) == 47


def test_meta_columns_present():
    assert len(META_COLUMNS) == 10
    assert set(META_COLUMNS).issubset(set(ALL_COLUMNS))
