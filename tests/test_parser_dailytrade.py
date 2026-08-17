from crawler.daily_trade.parser import parse_daily_trade, parse_daily_top_players, PlayerTarget


HTML_TRADE = """
<html><body>
<table id="dailytrade-table">
  <thead>
    <tr>
      <th>선수명</th>
      <th>평균가</th>
      <th>최고가</th>
      <th>최저가</th>
      <th>거래량</th>
      <th>강화</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td class="player">손흥민</td>
      <td>55조 1,000억</td>
      <td>60조</td>
      <td>50조</td>
      <td>123</td>
      <td>+9</td>
    </tr>
    <tr>
      <td class="player">Harry Kane</td>
      <td>1,234억</td>
      <td>2,000억</td>
      <td>900억</td>
      <td>45</td>
      <td>+8</td>
    </tr>
  </tbody>
</table>
</body></html>
"""


HTML_TOP = """
<html><body>
<table id="top-players">
  <thead><tr><th>순위</th><th>선수</th><th>픽률</th></tr></thead>
  <tbody>
    <tr><td>1</td><td>손흥민</td><td>12.3%</td></tr>
    <tr><td>2</td><td>Harry Kane</td><td>9.8%</td></tr>
  </tbody>
</table>
</body></html>
"""


def test_parse_daily_trade_with_targets_and_fill_missing():
    targets = [
        PlayerTarget(spid=1001, name_kor="손흥민", name_eng="Heung-Min Son"),
        PlayerTarget(spid=1002, name_kor="해리 케인", name_eng="Harry Kane"),
        PlayerTarget(spid=1003, name_kor="케빈", name_eng="Kevin"),  # 미등장
    ]
    rows = parse_daily_trade(HTML_TRADE, "2023-08-01", targets)
    # 손흥민
    s = next(r for r in rows if r["spid"] == 1001)
    assert s["avg_price"] == 55100000000000
    assert s["max_price"] == 60000000000000
    assert s["min_price"] == 50000000000000
    assert s["trade_count"] == 123
    assert s["max_enhance_level"] == 9
    # Harry Kane
    k = next(r for r in rows if r["spid"] == 1002)
    assert k["avg_price"] == 123400000000
    assert k["max_price"] == 200000000000
    assert k["min_price"] == 90000000000
    assert k["trade_count"] == 45
    assert k["max_enhance_level"] == 8
    # Kevin 미등장 → 보강 행
    v = next(r for r in rows if r["spid"] == 1003)
    assert v["trade_count"] == 0
    assert v["avg_price"] is None


def test_parse_daily_top_players():
    rows = parse_daily_top_players(HTML_TOP, "2023-08-01")
    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["pick_rate"] == 12.3

