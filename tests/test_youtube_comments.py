import os
import tempfile
from types import SimpleNamespace

import pytest

from youtube_comments.filtering import is_spam_text, filter_spam
from youtube_comments.sampling import balanced_pair, sample_list
from youtube_comments.storage import init_db, upsert_comments
from youtube_comments.utils import parse_video_id
from youtube_comments.fetcher import Comment


def test_parse_video_id_variants():
    assert parse_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert (
        parse_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    )
    assert parse_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert parse_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert parse_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert parse_video_id("") is None


def test_is_spam_text():
    assert is_spam_text("check http://spam.com now") is True
    assert is_spam_text("visit www.example.com") is True
    assert is_spam_text("카톡 오픈채팅 들어오세요") is True
    assert is_spam_text("ㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋ") is True
    assert is_spam_text("정상 댓글입니다") is False


def test_filter_spam_list():
    items = [
        Comment("v1", "t1", "c1", "a", "ok", 0, None, None, False, None),
        Comment("v1", "t1", "c2", "a", "www.bad.com", 0, None, None, False, None),
    ]
    out = filter_spam(items)
    assert len(out) == 1 and out[0].comment_id == "c1"


def test_sampling():
    a = [Comment("v1", "t1", f"a{i}", None, "x", 0, None, None, False, None) for i in range(100)]
    b = [Comment("v2", "t2", f"b{i}", None, "x", 0, None, None, False, None) for i in range(50)]
    aa, bb = balanced_pair(a, b, seed=1)
    assert len(aa) == 50 and len(bb) == 50
    s = sample_list(a, 10, seed=123)
    assert len(s) == 10 and len({c.comment_id for c in s}) == 10


def test_sqlite_storage_roundtrip(tmp_path):
    db = tmp_path / "comments.db"
    init_db(str(db))
    batch = [
        Comment("v1", "t1", "c1", "a", "ok1", 3, "2022-01-01T00:00:00Z", None, False, None),
        Comment("v1", "t1", "c2", "a", "ok2", 1, None, None, True, "c1"),
    ]
    n1 = upsert_comments(str(db), batch)
    n2 = upsert_comments(str(db), batch)  # ignore duplicates
    assert n1 >= 0
    assert n2 == 0
