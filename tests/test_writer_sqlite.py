from pathlib import Path
import sqlite3

from crawler.daily_trade.writer import connect, init_schema, upsert_daily_trade, is_visited, mark_visited


def test_writer_upsert_and_visited_log(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = connect(db)
    init_schema(conn)

    rows = [
        {
            "date": "2023-08-01",
            "spid": 1001,
            "player_name": "손흥민",
            "avg_price": 55100000000000,
            "max_price": 60000000000000,
            "min_price": 50000000000000,
            "trade_count": 123,
            "max_enhance_level": 9,
            "source": "web",
        }
    ]
    n1 = upsert_daily_trade(conn, rows)
    assert n1 == 1

    # UPSERT with changed values
    rows2 = [dict(rows[0], avg_price=55100000000001)]
    n2 = upsert_daily_trade(conn, rows2)
    assert n2 == 1

    # Read back and verify replaced
    cur = conn.cursor()
    cur.execute("SELECT avg_price FROM daily_trade WHERE date=? AND spid=?", ("2023-08-01", 1001))
    v = cur.fetchone()[0]
    assert v == 55100000000001

    # visited_log
    key = "dailytrade:20230801:trade"
    assert is_visited(conn, key) is False
    mark_visited(conn, key)
    assert is_visited(conn, key) is True

