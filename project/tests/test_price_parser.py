from app.price_parser import korean_money_to_int


def test_plain_digits():
    assert korean_money_to_int("9,850,000,000") == 9850000000
    assert korean_money_to_int("7800000000") == 7800000000


def test_eok_only():
    assert korean_money_to_int("457억") == 457 * 100_000_000
    assert korean_money_to_int("4,040억") == 4040 * 100_000_000


def test_jo_only():
    assert korean_money_to_int("7,250조") == 7250 * 1_000_000_000_000
    assert korean_money_to_int("4,040조") == 4040 * 1_000_000_000_000


def test_jo_eok_combo():
    assert korean_money_to_int("1조 4,900억") == 1_000_000_000_000 + 4900 * 100_000_000
    assert korean_money_to_int("2조 10억") == 2_000_000_000_000 + 10 * 100_000_000


def test_more_cases_and_fallbacks():
    assert korean_money_to_int("3,890조") == 3890 * 1_000_000_000_000
    assert korean_money_to_int("0") == 0
    assert korean_money_to_int("약 9,850,000,000 원") == 9850000000
    assert korean_money_to_int("") is None
    assert korean_money_to_int(None) is None

