"""홈택스 모의계산 사례 파일 형식 검사 (필수 칸, 값 타입, 캡처 이름).

    python3 eval/cases/hometax-2025/check_cases.py

표준 라이브러리만 쓴다. 값이 맞는지는 보지 않는다(값은 사람이 캡처와 대조한다).
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIRED = [
    "id",
    "status",
    "review",
    "tax_year",
    "source",
    "kind",
    "groups",
    "household",
    "plan",
    "question",
    "allocation",
    "inputs",
    "expected",
    "not_run",
    "notes",
]
GROUPS = {"basic_flow", "dependents", "child", "medical", "education", "card"}
STATUSES = {"draft", "confirmed"}
PEOPLE = {"husband", "wife"}
# README의 단계 이름표와 같아야 한다.
STAGES = {
    "gross_salary",
    "earned_income_deduction",
    "earned_income_amount",
    "basic_deduction_count",
    "basic_deduction_self",
    "basic_deduction_dependents_count",
    "basic_deduction_dependents",
    "additional_deduction_disabled_count",
    "additional_deduction_elderly_count",
    "additional_deduction_elderly",
    "additional_deduction_woman",
    "personal_deduction_total",
    "pension_insurance_deduction",
    "insurance_premium_deduction",
    "special_income_deduction_total",
    "income_after_deductions",
    "card_deduction",
    "other_income_deduction",
    "comprehensive_limit_excess",
    "income_deduction_total",
    "taxable_income",
    "marginal_rate_percent",
    "computed_tax",
    "tax_reduction_total",
    "earned_income_credit",
    "child_credit_age8plus_count",
    "child_credit_birth_count",
    "child_credit_age8plus",
    "child_credit_birth",
    "medical_credit_base",
    "medical_credit",
    "education_credit_base",
    "education_credit",
    "special_tax_credit_total",
    "tax_credit_total",
    "determined_tax",
    "refund_or_payment",
}


def check(path: Path) -> list[str]:
    errs: list[str] = []
    try:
        case = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"JSON 파싱 실패: {e}"]
    for key in REQUIRED:
        if key not in case:
            errs.append(f"필수 칸 없음: {key}")
    if errs:
        return errs
    if case["status"] not in STATUSES:
        errs.append(f"status는 {sorted(STATUSES)} 중 하나: {case['status']}")
    review = case["review"]
    if not isinstance(review, dict) or not {"reviewer", "date"} <= review.keys():
        errs.append("review에 reviewer, date 칸 필요")
    elif case["status"] == "confirmed" and not (review["reviewer"] and review["date"]):
        errs.append("confirmed면 review.reviewer와 review.date를 채워야 함")
    if case["tax_year"] != 2025:
        errs.append(f"tax_year는 2025: {case['tax_year']}")
    src = case["source"]
    captures = src.get("captures") if isinstance(src, dict) else None
    if not (isinstance(src, dict) and src.get("tool") and src.get("run_date")):
        errs.append("source에 tool, run_date 필요")
    if not (isinstance(captures, dict) and set(captures) == PEOPLE):
        errs.append("source.captures는 husband, wife 두 칸을 가진 객체")
        captures = {"husband": [], "wife": []}
    if case["kind"] != "household":
        errs.append(f"kind는 household: {case['kind']}")
    if not case["groups"] or not set(case["groups"]) <= GROUPS:
        errs.append(f"groups는 {sorted(GROUPS)}의 부분집합: {case['groups']}")
    if not (isinstance(case["inputs"], dict) and PEOPLE <= case["inputs"].keys()):
        errs.append("inputs에 husband, wife 필요")
    not_run_list = case["not_run"] if isinstance(case["not_run"], list) else []
    not_run = {n.get("person") for n in not_run_list}
    if not isinstance(case["expected"], list) or not case["expected"]:
        errs.append("expected는 비지 않은 목록")
    else:
        seen: set[tuple[str, str]] = set()
        for i, exp in enumerate(case["expected"]):
            for key in ("person", "stage", "value", "capture", "screen_label"):
                if key not in exp:
                    errs.append(f"expected[{i}]에 {key} 없음")
            person, stage = exp.get("person"), exp.get("stage")
            if person not in PEOPLE:
                errs.append(f"expected[{i}].person은 husband/wife: {person!r}")
                continue
            if stage not in STAGES:
                errs.append(f"expected[{i}].stage가 단계 이름표에 없음: {stage!r}")
            if (person, stage) in seen:
                errs.append(f"expected[{i}] 같은 사람·단계 중복: {person} {stage}")
            seen.add((person, stage))
            value = exp.get("value")
            if not isinstance(value, int) or isinstance(value, bool):
                errs.append(f"expected[{i}].value는 정수: {value!r}")
            if exp.get("not_from_this_run"):
                if person not in not_run or not exp.get("basis"):
                    errs.append(
                        f"expected[{i}]는 not_from_this_run이면 not_run에 그 사람과 basis 필요"
                    )
            elif exp.get("capture") not in captures.get(person, []):
                cap = exp.get("capture")
                errs.append(f"expected[{i}].capture {cap!r}가 source.captures.{person}에 없음")
        people_with_det = {p for p, s in seen if s == "determined_tax"}
        if people_with_det != PEOPLE:
            errs.append(f"부부 둘 다 determined_tax가 있어야 함: {sorted(people_with_det)}")
    if not isinstance(case["notes"], list):
        errs.append("notes는 목록")
    return errs


def main() -> int:
    files = sorted(HERE.glob("*.json"))
    seen: dict[str, str] = {}
    failed = 0
    for path in files:
        errs = check(path)
        try:
            cid = json.loads(path.read_text(encoding="utf-8")).get("id")
        except json.JSONDecodeError:
            cid = None
        if cid in seen:
            errs.append(f"id 중복: {cid} ({seen[cid]})")
        elif cid:
            seen[cid] = path.name
        status = "OK " if not errs else "ERR"
        print(f"{status} {path.name}")
        for e in errs:
            print(f"    - {e}")
        failed += bool(errs)
    print(f"\n{len(files)}개 파일, 실패 {failed}개")
    return 1 if failed or not files else 0


if __name__ == "__main__":
    sys.exit(main())
