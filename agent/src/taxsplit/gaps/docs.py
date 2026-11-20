"""간소화 추출 결과(PR 12 형식)에서 빈 곳 찾기에 필요한 것만 읽는다."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from taxsplit.extract.models import ExtractedDoc, ExtractedItem

# 그 사람 이름으로 된 자료가 "있다"고 보는 그룹. 보험료(국민연금·건강보험 등)는 뺀다:
# 동의한 부양가족이라도 근로자 본인 불입분만 공제되는 항목은 부양가족 명의 자료를 주지 않는다
# (인쇄 369쪽 Q3). 그래서 이 항목이 비었다는 것으로 빈 곳을 판단하지 않는다
PERSON_GROUPS = frozenset({"medical", "education", "card"})


@dataclass(frozen=True)
class DocView:
    items: tuple[ExtractedItem, ...]

    def rows_of(self, name: str) -> list[ExtractedItem]:
        """그 사람 이름으로 된 의료비·교육비·카드 줄."""
        return [i for i in self.items if i.person_name == name and i.group in PERSON_GROUPS]

    def has_rows(self, name: str) -> bool:
        return bool(self.rows_of(name))

    def group(self, group: str) -> list[ExtractedItem]:
        return [i for i in self.items if i.group == group]

    def has_medical(self) -> bool:
        return bool(self.group("medical"))

    def has_kind(self, group: str, words: Iterable[str], name: str | None = None) -> bool:
        """그 그룹에 세부 종류 글자에 words 중 하나가 든 줄이 있나(name이 있으면 그 사람만)."""
        return any(
            any(w in i.kind for w in words)
            for i in self.group(group)
            if name is None or i.person_name == name
        )


def view(documents: Iterable[ExtractedDoc | dict[str, Any]]) -> DocView:
    """추출 결과 여러 부(남편·아내)를 한 목록으로 합친다."""
    items: list[ExtractedItem] = []
    for d in documents:
        doc = d if isinstance(d, ExtractedDoc) else ExtractedDoc.model_validate(d)
        items += doc.items
    return DocView(tuple(items))
