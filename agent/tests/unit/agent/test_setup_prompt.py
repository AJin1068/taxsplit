"""첫 화면 설정이 대화 상태·시스템 프롬프트에 들어간다(FR-09 호칭, FR-10 자녀 수)."""

from datetime import UTC, datetime

from taxsplit.agent.prompt import base_prompt, system_prompt
from taxsplit.agent.state import build_state
from taxsplit.domain.models import Conversation


def _state(self_role=None, child_count=None):
    conv = Conversation(
        title="t",
        created_at=datetime(2026, 11, 20, tzinfo=UTC),
        id=1,
        self_role=self_role,
        child_count=child_count,
    )
    return build_state(conv, [], [])


def test_state_carries_setup_to_sensor() -> None:
    state = _state("wife", 2)
    assert state.self_role == "wife" and state.child_count == 2
    assert state.sensor.self_role == "wife"


def test_prompt_names_user_me_and_spouse() -> None:
    prompt = system_prompt(_state("wife"))
    assert "사용자는 아내이다" in prompt and '배우자는 "남편"' in prompt
    prompt = system_prompt(_state("husband"))
    assert "사용자는 남편이다" in prompt and '배우자는 "아내"' in prompt


def test_prompt_has_chosen_child_count_including_zero() -> None:
    assert "공제 대상 자녀 수: 2명" in system_prompt(_state(child_count=2))
    assert "공제 대상 자녀 수: 0명" in system_prompt(_state(child_count=0))


def test_prompt_unchanged_without_setup() -> None:
    assert system_prompt(_state()) == base_prompt()
