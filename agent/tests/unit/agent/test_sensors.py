"""센서 3개 표: 막아야 할 답(센서별·금액 모양별)과 잡으면 안 되는 답 5가지(거짓 막음 0건)."""

import pytest

from taxsplit.agent.sensors import SensorContext, check_answer

BEST = [{"하늘": "husband", "봄": "wife"}, {"하늘": "wife", "봄": "wife"}]
# 엔진 결과에 있는 금액(예: 추가 환급액 472,150원)과 사용자가 말한 연봉
ENGINE = {472_150, 5_586_000, 5_915_000}
USER = {42_000_000}


def after() -> SensorContext:
    """배분 비교가 성공한 뒤."""
    return SensorContext(allowed=ENGINE | USER, names=["하늘", "봄"], best_assignments=BEST)


def before() -> SensorContext:
    """배분 비교 전(사용자 글 금액만 앎)."""
    return SensorContext(allowed=set(USER), names=["하늘", "봄"])


# (센서, 금액 모양, 답) — 모두 막혀야 한다
BLOCK = [
    ("amount", "1,234,567원", "환급이 512,300원 늘어요."),
    ("amount", "1234567원", "환급이 512300원 늘어요."),
    ("amount", "123만 원", "환급이 50만 원 늘어요."),
    ("amount", "123만원", "환급이 50만원 늘어요."),
    ("amount", "1억 2,000만 원", "합계 세금은 1억 2,000만 원이에요."),
    ("amount", "12만 3천 원", "차이는 12만 3천 원이에요."),
    ("verdict", "-", "봄 님은 남편 쪽에서 공제받으세요."),
    (
        "verdict",
        "-",
        "하늘이는 아내가 공제받고, 봄 님은 남편이 공제받으면 됩니다.\n봄은 남편 공제.",
    ),
    ("precalc", "판정", "봄 님은 아내 쪽에서 공제받는 게 좋아요."),
    ("precalc", "판정(호칭)", "어머니는 아내 쪽으로 공제하세요."),
    ("precalc", "금액", "아마 47만 원쯤 더 돌려받으실 거예요."),
]


@pytest.mark.parametrize(("sensor", "shape", "text"), BLOCK)
def test_blocks(sensor: str, shape: str, text: str) -> None:
    ctx = before() if sensor == "precalc" else after()
    failures = check_answer(text, ctx)
    assert failures, text
    assert {f.sensor for f in failures} == {sensor}


# 잡으면 안 되는 것 5가지(Issue #19 "하지 않을 것")
PASS = [
    ("사용자 금액 되묻기(계산 전)", before(), "아내 연봉 4,200만 원 맞으세요?"),
    (
        "질문·연도·나이·사람 수·경우의 수·비율",
        before(),
        "2025년 기준으로 부양가족 2명, 128가지를 볼게요. 70세 이상인지, 3% 넘는지 확인할게요. "
        "어머니 올해 소득이 있으세요?",
    ),
    ("엔진 금액 만 원 단위로", after(), "흔한 방식보다 47만 원, 반올림하면 48만 원 더 받아요."),
    ("두 쪽이 다 나오는 문장", after(), "하늘이는 남편과 아내 중 누가 공제받아도 같아요."),
    (
        "최적안 여럿 중 하나",
        after(),
        "하늘이는 아내 쪽에서 공제받으세요. 봄 님은 아내 쪽 공제예요.",
    ),
]


@pytest.mark.parametrize(("case", "ctx", "text"), PASS, ids=[p[0] for p in PASS])
def test_must_not_block(case: str, ctx: SensorContext, text: str) -> None:
    assert check_answer(text, ctx) == []


def test_engine_amount_exact_passes() -> None:
    assert check_answer("472,150원 더 돌려받아요.", after()) == []


def test_unknown_person_is_not_a_verdict() -> None:
    # 계산에 없는 이름은 판정으로 보지 않는다(질문을 막지 않게)
    assert check_answer("철수 님 공제는 남편 쪽이 좋을지 같이 볼게요.", after()) == []


def test_question_sentence_is_not_a_verdict_before_compare() -> None:
    assert check_answer("어머니를 아내 쪽에 공제하려면 소득을 알려 주실래요?", before()) == []
