import re
from typing import Iterable, List

from .fetcher import Comment


URL_RE = re.compile(r"(https?://|www\.)", re.IGNORECASE)
AD_KO_RE = re.compile(
    r"(카톡|카카오톡|오픈채팅|수익|한달수익|홍보|광고|성인|19금|텔레|텔레그램|t\.me|bit\.ly|프로모션)",
    re.IGNORECASE,
)


def is_spam_text(text: str) -> bool:
    if not text:
        return False
    if URL_RE.search(text):
        return True
    if AD_KO_RE.search(text):
        return True
    # simple repeated char spam (e.g., "ㅋㅋㅋㅋㅋㅋ" 10+)
    if re.search(r"(.)\1{7,}", text):
        return True
    return False


def filter_spam(comments: Iterable[Comment]) -> List[Comment]:
    return [c for c in comments if not is_spam_text(c.text)]

