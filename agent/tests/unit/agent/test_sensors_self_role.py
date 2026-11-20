"""판정 센서의 "나" 읽기(FR-09): 본인 입장을 골랐을 때만 "나 쪽에 공제"를 본인 쪽 판정으로 본다."""

import pytest

from taxsplit.agent.sensors import SensorContext, check_answer, verdict_of

NAMES = ["첫째", "어머니"]
# 최적안: 첫째는 아내, 어머니는 남편
BEST = [{"첫째": "wife", "어머니": "husband"}]


def ctx(self_role: str | None) -> SensorContext:
    return SensorContext(names=NAMES, best_assignments=BEST, self_role=self_role)


# 맞는 예: 최적안과 같아 통과해야 한다
@pytest.mark.parametrize(
    ("role", "text"),
    [
        ("wife", "첫째는 나 쪽에 공제하세요."),
        ("wife", "첫째는 내 쪽으로 공제받는 게 유리해요."),
        ("wife", "어머니는 남편 쪽에 공제하세요."),
        ("husband", "어머니는 나에게 공제하세요."),
        ("husband", "첫째는 아내 쪽에 공제하세요."),
    ],
)
def test_matching_self_verdict_passes(role: str, text: str) -> None:
    assert check_answer(text, ctx(role)) == []


# 틀린 예: 최적안과 달라 판정 센서가 멈춰야 한다
@pytest.mark.parametrize(
    ("role", "text"),
    [
        ("wife", "어머니는 나 쪽에 공제하세요."),
        ("husband", "첫째는 나 쪽에 공제하세요."),
        ("husband", "첫째는 나한테 공제하면 돼요."),
    ],
)
def test_wrong_self_verdict_stops(role: str, text: str) -> None:
    failures = check_answer(text, ctx(role))
    assert [f.sensor for f in failures] == ["verdict"]


def test_self_verdict_reads_as_role() -> None:
    assert verdict_of("첫째는 나 쪽에 공제", NAMES, "wife") == ("첫째", "wife")
    assert verdict_of("첫째는 나 쪽에 공제", NAMES, "husband") == ("첫째", "husband")


@pytest.mark.parametrize(
    "text",
    [
        "어머니는 나 쪽에 공제하세요.",
        "어머니는 나 쪽에 공제하고 남편 쪽은 아니에요.",
        "첫째는 나한테 공제하면 돼요.",
    ],
)
def test_without_self_role_me_sentence_is_not_verdict(text: str) -> None:
    # 본인 입장을 모르면 "나"를 어느 쪽으로도 읽지 않는다(잡으면 안 되는 경우)
    assert check_answer(text, ctx(None)) == []
    assert verdict_of(text, NAMES, None) is None


def test_me_and_other_side_in_one_sentence_is_comparison() -> None:
    # 두 쪽이 다 나오면 비교 설명일 수 있어 보지 않는다(기존 규칙 그대로)
    text = "어머니는 나 쪽보다 남편 쪽에 공제하는 게 나아요."
    assert verdict_of(text, NAMES, "wife") is None


def test_words_containing_na_are_not_self() -> None:
    # "나머지"·"하나"의 "나"는 본인이 아니다
    text = "나머지 하나는 남편 쪽에 공제하세요. 어머니는 남편 쪽에 공제."
    assert check_answer(text, ctx("wife")) == []


def test_self_verdict_before_compare_is_precalc() -> None:
    before = SensorContext(names=NAMES, self_role="wife")
    failures = check_answer("첫째는 나 쪽에 공제하세요.", before)
    assert [f.sensor for f in failures] == ["precalc"]
