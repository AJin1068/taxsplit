"""사례 실행 한 번(Run)과 본인 정보 만들기. 국세청·홈택스 변환이 같이 쓴다(테스트 쪽에만 둔다)."""

from dataclasses import dataclass, field
from typing import Any

from taxsplit.engine import SelfInfo, WorkerInput


@dataclass
class Run:
    """엔진 실행 한 번(사람 한 명 또는 질문 하나)과 그에 딸린 기대값 줄."""

    label: str
    expected: list[dict[str, Any]]
    worker: WorkerInput | None = None
    # 이 부양가족 한 명의 값을 묻는 사례(p99·p100)면 그 이름
    target: str | None = None
    # 사례가 산출세액·총급여를 입력으로 주는 경우(p162): 근로소득세액공제만 비교
    credit_inputs: tuple[int, int] | None = None
    gross_is_input: bool = False
    excluded: list[dict[str, Any]] = field(default_factory=list)
    # 의료비·교육비·카드 항목 사례면 그 계산만 부른다(medical | education | card)
    item: str | None = None
    # 보충 입력·공제 대상 여부가 confirmed가 아니라 돌리지 못한 기대값 줄("입력 부족")
    missing: list[dict[str, Any]] = field(default_factory=list)


def person_of(me: dict, family_has_spouse: bool = False) -> SelfInfo:
    """본인 정보. 성별·출생연도는 문서나 보충 입력에 꼭 있어야 한다(없으면 KeyError).

    배우자 유무가 둘 다에 없으면 문서 가족 목록에 배우자가 있나로 본다(p095·p212 사례).
    """
    has_spouse = me["has_spouse"] if "has_spouse" in me else family_has_spouse
    return SelfInfo(sex=me["sex"], birth_year=me["birth_year"], has_spouse=has_spouse)


def worker_of(gross: int, person: SelfInfo, deps=(), **kw) -> WorkerInput:
    return WorkerInput(gross_salary=gross, person=person, dependents=tuple(deps), **kw)
