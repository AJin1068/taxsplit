"""키워드 검색(BM25)을 직접 구현한다. 새 의존성 없이 69쪽 규모를 메모리에서 돈다.

한국어는 띄어쓰기가 들쭉날쭉하고 조사가 붙으므로("의료비는", "의료비를"),
공백 단어와 함께 글자 2개씩 묶은 것(2-gram)도 단어로 쓴다. "의료비는" → 의료, 료비, 비는.
"""

import math
import re
from collections import Counter

# 일반적인 BM25 기본값(운영값, 세법 숫자 아님)
K1 = 1.5
B = 0.75

_WORD = re.compile(r"[0-9A-Za-z가-힣]+")


def tokenize(text: str) -> list[str]:
    """글을 검색 단어로: 공백 단어(소문자) + 한글·숫자 글자 2-gram."""
    tokens: list[str] = []
    for word in _WORD.findall(text.lower()):
        tokens.append(word)
        if len(word) > 2:
            tokens.extend(word[i : i + 2] for i in range(len(word) - 1))
    return tokens


class BM25:
    """문서 목록을 받아 두고 질문마다 문서별 점수를 낸다."""

    def __init__(self, docs: list[str], k1: float = K1, b: float = B) -> None:
        self.k1 = k1
        self.b = b
        self._tfs = [Counter(tokenize(d)) for d in docs]
        self._lens = [sum(tf.values()) for tf in self._tfs]
        self._avg = (sum(self._lens) / len(self._lens)) if self._lens else 0.0
        df: Counter[str] = Counter()
        for tf in self._tfs:
            df.update(tf.keys())
        n = len(docs)
        # 드문 단어일수록 큰 가중치(idf). +1로 음수가 되지 않게 한다
        self._idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, query: str) -> list[float]:
        """문서마다 질문과 얼마나 맞는지 점수. 순서는 받은 문서 순서와 같다."""
        terms = Counter(tokenize(query))
        out: list[float] = []
        for tf, length in zip(self._tfs, self._lens, strict=True):
            norm = self.k1 * (1 - self.b + self.b * length / self._avg) if self._avg else self.k1
            score = 0.0
            for term, qcount in terms.items():
                f = tf.get(term, 0)
                if f:
                    score += qcount * self._idf[term] * f * (self.k1 + 1) / (f + norm)
            out.append(score)
        return out
