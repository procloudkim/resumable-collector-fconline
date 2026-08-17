import os
from pathlib import Path
import importlib
import subprocess
import sys
import sqlite3
import pytest


@pytest.mark.smoke
def test_cache_init_schema_creates_tables(tmp_path, monkeypatch):
    # Use temporary DB path
    db_path = tmp_path / "data.db"
    # Monkeypatch app.core.cache.DB_PATH to our temp path if present
    cache = importlib.import_module("app.core.cache")
    monkeypatch.setattr(cache, "DB_PATH", db_path, raising=False)
    cache.init_schema()
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN (?,?,?)",
                    ("ouid_map", "ranker_stats", "seen_match"))
        names = {r[0] for r in cur.fetchall()}
        assert {"ouid_map", "ranker_stats"}.issubset(names)


@pytest.mark.smoke
def test_price_to_int_basic():
    parser = importlib.import_module("crawler.daily_trade.parser")
    assert parser.price_to_int("123") == 123
    assert parser.price_to_int("300,000") == 300000
    # Fallback strips non-digits
    assert parser.price_to_int("BP 1,234,567") == 1234567


@pytest.mark.smoke
def test_demo_data_script_generates_csv(tmp_path, monkeypatch):
    # Run demo script to generate minimal CSV
    root = Path(__file__).resolve().parents[1]
    proc = root / "data" / "processed"
    # Move processed dir to tmp and point working dir
    monkeypatch.chdir(root)
    # Ensure empty processed dir
    if proc.exists():
        for p in proc.glob("*"):
            if p.is_file():
                p.unlink()
    ret = subprocess.run([sys.executable, "scripts/demo_data.py", "--quiet"], check=True)
    assert ret.returncode == 0
    out = proc / "top10_trend.csv"
    assert out.exists()
    assert out.read_text(encoding="utf-8").count("\n") >= 2

