from app.core.cache import init_schema, set_ouid, get_ouid, is_seen, mark_seen

def test_cache_roundtrip(tmp_path, monkeypatch):
    # 임시 DB 사용
    monkeypatch.setattr("app.core.cache.DB_PATH", tmp_path / "test.db")
    init_schema()
    set_ouid("홍길동", "OU123")
    assert get_ouid("홍길동") == "OU123"
    assert not is_seen("m1")
    mark_seen("m1")
    assert is_seen("m1")
