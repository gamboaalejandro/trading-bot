"""Research configuration and data provenance (PLAN R00)."""
from pathlib import Path

import pytest
import yaml

from apps.research import config as rconfig
from apps.research.config import ConfigError, get_config, load_config
from apps.research.data import manifest


def test_default_config_loads_and_respects_user_limits():
    cfg = load_config()
    assert cfg.budget.total == 40
    assert sum(cfg.budget.quotas.values()) == 40
    assert cfg.budget.quotas["DEBATE"] == 8
    assert cfg.budget.exploratory_tag == "debate-exploratorio"
    assert cfg.leverage["margin_type"] == "ISOLATED"
    assert cfg.leverage["max_alt"] <= 1.0
    assert cfg.leverage["max_major"] <= 1.5
    assert cfg.leverage["user_hard_cap"] <= 3.0
    assert cfg.gate["max_dd_oos_spot"] <= 0.20
    assert cfg.gate["max_dd_oos_futures"] <= 0.20
    assert cfg.sizing["gross_long_max"] <= 1.0
    assert cfg.funding_excluded == ("BNBUSDT",)
    assert cfg.splits["walk_forward"]["n_folds"] == 17
    assert cfg.trials_log.is_absolute()


def test_sources_match_manifest():
    cfg = get_config()
    for market in ("spot", "futures", "funding"):
        assert cfg.source_commit(market) == manifest.source_commit(market)


def test_data_root_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv(rconfig.DATA_ROOT_ENV, str(tmp_path))
    assert get_config().data_root == tmp_path
    monkeypatch.delenv(rconfig.DATA_ROOT_ENV)
    assert get_config().data_root == Path("/home/user/harness/data")


def _write_variant(tmp_path, mutate):
    raw = yaml.safe_load(rconfig.CONFIG_PATH.read_text(encoding="utf-8"))
    mutate(raw)
    p = tmp_path / "research.yml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return p


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r["leverage"].update(max_major=4.0),
        lambda r: r["leverage"].update(margin_type="CROSSED"),
        lambda r: r["gate"].update(max_dd_oos_spot=0.25),
        lambda r: r["budget"]["quotas"].update(TREND=6),
        lambda r: r["sizing"].update(gross_long_max=1.5),
        lambda r: r.pop("budget"),
    ],
)
def test_invalid_configs_rejected(tmp_path, mutate):
    with pytest.raises(ConfigError):
        load_config(_write_variant(tmp_path, mutate))


def test_missing_config_file(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yml")


def test_manifest_hashes(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("x\n1\n")
    b.write_text("x\n2\n")
    m1 = manifest.build_manifest([b, a], root=tmp_path)
    assert list(m1["files"]) == ["a.csv", "b.csv"]
    assert m1["sources"] == manifest.data_commit()
    a.write_text("x\n3\n")
    m2 = manifest.build_manifest([a, b], root=tmp_path)
    assert m2["files"]["a.csv"] != m1["files"]["a.csv"]
    assert m2["digest"] != m1["digest"]
