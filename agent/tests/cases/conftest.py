"""사례 비교가 끝나면 그룹별·출처별 표를 출력한다(uv run pytest tests/cases -q)."""

from collections import Counter

from cases.case_compare import all_rows

GROUP_ORDER = ["기본 흐름", "부양가족", "자녀", "의료비", "교육비", "카드"]


def pytest_terminal_summary(terminalreporter):
    rows = all_rows()
    tr = terminalreporter
    tr.section("사례 비교 (PR 4)")
    tr.write_line("| 출처 | 그룹 | 일치 | 비교 | PR 5로 미룸 | 입력으로 씀 | 제외 |")
    tr.write_line("| --- | --- | --- | --- | --- | --- | --- |")
    for source in ("국세청 사례", "홈택스"):
        for group in GROUP_ORDER:
            mine = [r for r in rows if r.source == source and r.group == group]
            if not mine:
                continue
            c = Counter(r.kind for r in mine)
            ok = sum(r.ok for r in mine)
            tr.write_line(
                f"| {source} | {group} | {ok} | {c['compare']} | {c['deferred']} "
                f"| {c['input']} | {c['excluded']} |"
            )
    bad = [r for r in rows if r.kind == "compare" and not r.ok]
    # 1원 미만 차이 = 끝수 의심. 엔진 값은 원 단위 정수라 생기면 사례 쪽 소수를 의심한다
    rounding = [r for r in bad if _diff(r) is not None and 0 < abs(_diff(r)) < 1]
    tr.write_line(f"불일치 {len(bad)}건 (끝수 의심 {len(rounding)}건)")
    for r in bad:
        tr.write_line(
            f"  - {r.case} {r.stage}: 기대 {r.expected} / 엔진 {r.actual} / 차이 {_diff(r)}"
        )


def _diff(r):
    if isinstance(r.expected, bool) or not isinstance(r.expected, (int, float)):
        return None
    return r.actual - r.expected
