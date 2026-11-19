"""대화 상태: 요청 사이에 서버 메모리에 두지 않고, 턴마다 저장소에서 다시 만든다(FR-08).

저장된 메시지(글)와 도구 호출 기록만으로 만든다. 그래서 서버를 다시 켜도 대화를 이어 간다.
"""

from dataclasses import dataclass, field
from typing import Any

from taxsplit.agent.money import extract_amounts, ints_in
from taxsplit.agent.sensors import SensorContext
from taxsplit.allocation.models import Household
from taxsplit.domain.models import Conversation, Message
from taxsplit.tools.definitions import CHECK_ELIGIBILITY, COMPARE_ALLOCATIONS
from taxsplit.tools.records import ToolCallRecord
from taxsplit.tools.status import ToolStatus
from taxsplit.tools.validation import family_fingerprint, validate_household


@dataclass
class ConversationState:
    conversation_id: int
    # 이번 턴 번호 = 그 대화의 사용자 메시지 순번
    turn: int
    history: list[Message] = field(default_factory=list)
    documents: list[dict[str, Any]] = field(default_factory=list)
    # 요건 확인이 성공한 가족 지문(검사기 순서 규칙용)
    checked: set[str] = field(default_factory=set)
    # 가장 최근 성공한 도구 인자(가구 JSON). 시스템 프롬프트 끝에 붙인다
    last_args: Any = None
    # 배분 비교가 이 대화에서 한 번이라도 성공했나
    computed: bool = False
    # 가장 최근 성공한 배분 비교 결과와 그 가구
    last_compare: dict[str, Any] | None = None
    last_compare_household: Household | None = None
    sensor: SensorContext = field(default_factory=SensorContext)

    def absorb(self, record: ToolCallRecord) -> None:
        """성공한 도구 호출 하나를 상태에 반영한다(지난 턴 기록, 이번 턴 새 기록 모두)."""
        if record.status != ToolStatus.OK:
            return
        household, _ = validate_household(record.args)
        if household is None:  # 성공한 호출이면 인자가 늘 맞지만, 저장된 값이 바뀐 경우를 막는다
            return
        self.last_args = record.args
        self.sensor.allowed |= ints_in(record.args) | ints_in(record.result)
        self.sensor.names = [m.name for m in household.members]
        if record.tool == CHECK_ELIGIBILITY:
            self.checked.add(family_fingerprint(household))
        elif record.tool == COMPARE_ALLOCATIONS and record.result is not None:
            self.computed = True
            self.last_compare = record.result
            self.last_compare_household = household
            self.sensor.best_assignments = list(record.result.get("best_assignments", []))

    def add_user_text(self, text: str) -> None:
        """사용자가 쓴 금액은 답에 다시 써도 된다("4,200만 원 맞으세요?")."""
        self.sensor.allowed |= {v for _, v in extract_amounts(text)}


def build_state(
    conversation: Conversation,
    messages: list[Message],
    records: list[ToolCallRecord],
) -> ConversationState:
    assert conversation.id is not None
    users = [m for m in messages if m.role == "user"]
    state = ConversationState(
        conversation_id=conversation.id,
        turn=len(users) + 1,
        history=list(messages),
        documents=list(conversation.documents or []),
    )
    state.sensor.allowed |= ints_in(state.documents)
    for m in users:
        state.add_user_text(m.content)
    for record in records:
        state.absorb(record)
    return state


def members_of(household: Household) -> list[dict[str, Any]]:
    """allocation 이벤트의 members: 그 계산에 쓴 부양가족의 이름·관계·출생연도."""
    return [
        {
            "name": m.name,
            "relation": m.dependent.relation,
            "birth_year": m.dependent.birth_year,
        }
        for m in household.members
    ]
