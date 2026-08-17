import random
from typing import Iterable, List, Sequence, Tuple

from .fetcher import Comment


def sample_list(items: Sequence[Comment], n: int, seed: int = 42) -> List[Comment]:
    if n >= len(items):
        return list(items)
    rnd = random.Random(seed)
    return rnd.sample(list(items), n)


def balanced_pair(
    a: Sequence[Comment], b: Sequence[Comment], seed: int = 42
) -> Tuple[List[Comment], List[Comment]]:
    n = min(len(a), len(b))
    return sample_list(a, n, seed), sample_list(b, n, seed)

