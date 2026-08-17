from unittest.mock import patch, MagicMock
from app.services.images import ensure_player_image, player_image_url

def test_player_image_url():
    assert "players/big/1234.png" in player_image_url(1234)

@patch("app.services.images.requests.get")
def test_ensure_player_image(mock_get, tmp_path, monkeypatch):
    # 임시폴더로 IMG_DIR 바꾸기
    monkeypatch.setattr("app.services.images.IMG_DIR", tmp_path)
    # 가짜 응답
    resp = MagicMock()
    resp.status_code = 200
    resp.content = b"PNGDATA"
    mock_get.return_value = resp
    p = ensure_player_image(999)
    assert p and p.exists()
