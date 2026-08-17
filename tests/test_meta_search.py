from app.services.meta import normalize_name, search_player_by_name

def test_normalize_name_basic():
    assert normalize_name(" 앨런-시어러 ") == normalize_name("앨런 시어러")
    assert normalize_name("Son  Heung-Min") == "sonheungmin"

def test_search_player_name_empty():
    assert search_player_by_name("") == []

# 실제 spid.json 내용에 따라 아래는 달라짐.
# spid.json이 로컬에 다운로드된 이후에만 동작함(또는 mock)
# def test_search_player_by_name_fuzzy():
#     results = search_player_by_name("손흥", fuzzy=True, limit=50)
#     assert isinstance(results, list)
