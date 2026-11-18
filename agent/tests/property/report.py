"""성질 테스트 결과 표: 성질별 위반 건수, 가구 분포. pytest 끝에 conftest가 출력한다."""

from collections import Counter
from itertools import pairwise

from property.checks import PROPERTIES, Violation
from taxsplit.engine import Rulebook, basic_eligibility
from taxsplit.synth import SynthHousehold

# pytest가 끝날 때 출력할 줄(표 단위로 쌓는다)
LINES: list[str] = []

# 분포 표의 총급여 구간(만원). 생성 범위를 나눠 보는 눈금일 뿐 세법 구간이 아니다
GROSS_EDGES = (2_000, 4_000, 6_000, 8_000, 10_000, 12_000, 15_000)


def violation_table(violations: list[Violation], n_households: int, seconds: float) -> list[str]:
    """성질별 위반 건수와 어긴 가구(시드·남편/아내·단계)."""
    count = Counter(v.prop for v in violations)
    lines = [
        f"### 성질 테스트: 가구 {n_households:,}개(근로자 {2 * n_households:,}명), {seconds:.1f}초",
        "",
        "| 성질 | 내용 | 위반 건수 |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {p} | {text} | {count[p]} |" for p, text in PROPERTIES.items()]
    for v in violations[:50]:
        lines.append(f"- 위반: seed={v.seed} {v.who} 성질{v.prop} 단계={v.stage} ({v.detail})")
    return lines


def distribution_table(households: list[SynthHousehold], rules) -> list[str]:
    """총급여 구간별 근로자 수, 부양가족 수별 가구 수, 요건 미달 부양가족 비율."""
    book = Rulebook(rules)
    gross = Counter()
    for hh in households:
        for w in (hh.husband, hh.wife):
            man = w.gross_salary // 10_000
            label = next(f"{lo:,}~{hi:,}만원" for lo, hi in pairwise(GROSS_EDGES) if man <= hi)
            gross[label] += 1
    n_deps = Counter(len(hh.dependents) for hh in households)
    deps = [d for hh in households for d in hh.dependents]
    failed = Counter(
        basic_eligibility(d, book)[1] for d in deps if not basic_eligibility(d, book)[0]
    )
    lines = ["### 생성 가구 분포", "", "| 총급여 구간 | 근로자 수 |", "| --- | --- |"]
    lines += [
        f"| {k} | {gross[k]} |"
        for k in sorted(gross, key=lambda s: int(s.split("~")[0].replace(",", "")))
    ]
    lines += ["", "| 부양가족 수 | 가구 수 |", "| --- | --- |"]
    lines += [f"| {k}명 | {n_deps[k]} |" for k in sorted(n_deps)]
    total_failed = sum(failed.values())
    ratio = total_failed / len(deps) if deps else 0.0
    lines += ["", f"요건 미달 부양가족: {total_failed} / {len(deps)}명 ({ratio:.1%})"]
    lines += [f"- {reason}: {n}명" for reason, n in failed.most_common()]
    return lines
