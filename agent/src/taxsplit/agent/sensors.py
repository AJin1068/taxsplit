"""서비스 안 센서 3개: AI의 최종 답을 보내기 전에 코드가 검사한다(design.md 5장, FR-06).

- 금액 센서(amount): 답의 금액이 허용 목록(사용자 글·추출 자료·성공한 도구 인자와 결과) 안인가
- 판정 센서(verdict): "OO는 남편/아내 쪽에 공제"가 배분 비교 최적안과 같은가
- 계산 전 답 금지(precalc): 배분 비교가 한 번도 성공하지 않았는데 판정·모르는 금액을 말하는가
"""

import re
from dataclasses import dataclass, field
from typing import Literal

from taxsplit.agent.money import allowed_with_rounding, unknown_amounts

type SensorName = Literal["amount", "verdict", "precalc"]

SIDES = {"husband": "남편", "wife": "아내"}

# 배분 비교 전에는 가족 이름을 모를 수 있어, 흔한 가족 호칭도 "가족"으로 본다(계산 전 답 금지 전용)
# TODO(사람 확인): docs/assumptions.md A-030
FAMILY_WORDS = (
    "어머니",
    "아버지",
    "어머님",
    "아버님",
    "장인",
    "장모",
    "시어머니",
    "시아버지",
    "자녀",
    "아들",
    "딸",
    "첫째",
    "둘째",
    "셋째",
)

_SENTENCE_END = re.compile(r"(?<=[.!?。])\s+|\n+")


@dataclass(frozen=True)
class SensorFailure:
    sensor: SensorName
    detail: str


@dataclass
class SensorContext:
    """센서가 보는 대화 상태. 루프가 턴마다 채운다."""

    # 허용 금액(만 원 단위로 줄인 값은 센서가 더한다)
    allowed: set[int] = field(default_factory=set)
    # 가족 이름(가장 최근 성공한 도구 인자의 members)
    names: list[str] = field(default_factory=list)
    # 가장 최근 성공한 배분 비교의 최적안 목록(같은 합계 안이 여럿일 수 있음). 없으면 None
    best_assignments: list[dict[str, str]] | None = None


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]


def _names_in(sentence: str, names: list[str]) -> list[str]:
    """문장에 나온 이름. 긴 이름부터 찾고 지워서 "시어머니" 안의 "어머니"를 두 번 세지 않는다."""
    found = []
    rest = sentence
    for name in sorted(set(names), key=len, reverse=True):
        if name and name in rest:
            found.append(name)
            rest = rest.replace(name, " ")
    return found


def verdict_of(sentence: str, names: list[str]) -> tuple[str, str] | None:
    """판정 문장이면 (이름, 'husband'|'wife'). 아니면 None.

    판정 문장: 질문이 아니고, 이름 하나 + "남편"·"아내" 중 하나만 + "공제"가 있다.
    두 쪽이 다 나오는 문장은 비교 설명일 수 있어 보지 않는다.
    TODO(사람 확인): docs/assumptions.md A-037
    """
    if sentence.rstrip().endswith("?") or "공제" not in sentence:
        return None
    found = _names_in(sentence, names)
    sides = [k for k, word in SIDES.items() if word in sentence]
    if len(found) != 1 or len(sides) != 1:
        return None
    return found[0], sides[0]


def check_answer(text: str, ctx: SensorContext) -> list[SensorFailure]:
    """떨어진 이유 목록. 빈 목록이면 통과."""
    computed = ctx.best_assignments is not None
    failures: list[SensorFailure] = []

    # 금액: 계산 전이면 계산 전 답 금지로, 계산 뒤면 금액 센서로 센다
    allowed = allowed_with_rounding(ctx.allowed)
    for raw, _ in unknown_amounts(text, allowed):
        sensor: SensorName = "amount" if computed else "precalc"
        failures.append(
            SensorFailure(sensor, f"'{raw}'은(는) 사용자 글·자료·도구 결과에 없는 금액입니다")
        )

    names = ctx.names if computed else [*ctx.names, *FAMILY_WORDS]
    for sentence in sentences(text):
        verdict = verdict_of(sentence, names)
        if verdict is None:
            continue
        name, side = verdict
        if not computed:
            failures.append(
                SensorFailure(
                    "precalc",
                    f"배분 비교(compare_allocations) 전에 '{sentence}'처럼 공제할 쪽을 말했습니다",
                )
            )
            continue
        assert ctx.best_assignments is not None
        if not any(a.get(name) == side for a in ctx.best_assignments):
            best = ", ".join(
                SIDES.get(a.get(name, ""), "공제 대상 아님") for a in ctx.best_assignments
            )
            failures.append(
                SensorFailure(
                    "verdict",
                    f"'{sentence}'는 최적안과 다릅니다(최적안에서 {name}: {best})",
                )
            )
    return failures


def feedback(failures: list[SensorFailure]) -> str:
    """AI에게 돌려줄 다시 쓰기 지시."""
    labels = {"amount": "금액 센서", "verdict": "판정 센서", "precalc": "계산 전 답 금지"}
    lines = "\n".join(f"- {labels[f.sensor]}: {f.detail}" for f in failures)
    return (
        "[시스템 검사] 답을 보내기 전 검사에서 걸렸습니다. 아래를 고쳐 답 전체를 다시 쓰세요. "
        "금액은 도구 결과·사용자 글에 있는 값만 쓰고, 공제할 쪽은 compare_allocations 최적안대로 "
        "말하세요. 아직 계산 전이면 판정·금액 대신 필요한 정보를 물으세요.\n" + lines
    )
