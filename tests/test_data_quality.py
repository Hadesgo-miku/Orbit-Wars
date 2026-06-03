"""data_quality 检查函数正负例测试。"""
from __future__ import annotations

import pandas as pd
import pytest

from eval.data_quality import (
    DataQualityThresholds,
    check_feature_schema,
    check_label_balance,
    check_no_nan_inf,
    check_resolve_rate,
)
from tuning.replay_scraper.extract_features import FEATURE_NAMES


def _base_row(**kwargs) -> dict:
    row = {c: 0.0 for c in FEATURE_NAMES}
    row.update(
        {
            "episode_id": 1,
            "tick": 10,
            "player_id": 0,
            "players_count": 2,
            "winner_id": 0,
            "source_id": 0,
            "target_id": 1,
            "ships": 5,
            "ships_frac": 0.5,
            "label_act": 1,
        }
    )
    row.update(kwargs)
    return row


def test_check_resolve_rate_pass():
    df = pd.DataFrame([_base_row(), _base_row(target_id=2)])
    r = check_resolve_rate(df, DataQualityThresholds())
    assert r.passed


def test_check_resolve_rate_fail():
    df = pd.DataFrame([_base_row(target_id=-1, label_act=1)])
    r = check_resolve_rate(df, DataQualityThresholds())
    assert not r.passed


def test_check_feature_schema_pass():
    df = pd.DataFrame([_base_row()])
    r = check_feature_schema(df, FEATURE_NAMES)
    assert r.passed


def test_check_feature_schema_fail():
    row = _base_row()
    del row["g_step_norm"]
    df = pd.DataFrame([row])
    r = check_feature_schema(df, FEATURE_NAMES)
    assert not r.passed


def test_check_no_nan_inf_pass():
    df = pd.DataFrame([_base_row()])
    r = check_no_nan_inf(df)
    assert r.passed


def test_check_no_nan_inf_fail():
    row = _base_row()
    row["g_step_norm"] = float("nan")
    df = pd.DataFrame([row])
    r = check_no_nan_inf(df)
    assert not r.passed


def test_check_label_balance_pass():
    rows = [_base_row(label_act=1)] * 95 + [_base_row(label_act=0, source_id=-1, target_id=-1)] * 5
    df = pd.DataFrame(rows)
    r = check_label_balance(df, DataQualityThresholds())
    assert r.passed


def test_check_label_balance_fail_all_idle():
    df = pd.DataFrame([_base_row(label_act=0, source_id=-1, target_id=-1)] * 10)
    r = check_label_balance(df, DataQualityThresholds())
    assert not r.passed


def test_check_label_balance_fail_no_idle():
    df = pd.DataFrame([_base_row(label_act=1)] * 10)
    r = check_label_balance(df, DataQualityThresholds())
    assert not r.passed
