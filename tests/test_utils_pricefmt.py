from crawler.daily_trade.parser import price_to_int


def test_price_to_int_basic_cases():
    assert price_to_int("55조 1,000억") == 55100000000000
    assert price_to_int("60조") == 60000000000000
    assert price_to_int("1,234억") == 123400000000
    assert price_to_int("123,456,789") == 123456789
    assert price_to_int("") is None
    assert price_to_int(None) is None

