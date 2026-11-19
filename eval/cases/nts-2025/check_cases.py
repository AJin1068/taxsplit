"""국세청 책자 사례 파일 형식 검사 (필수 칸 존재, 값 타입).

    python3 eval/cases/nts-2025/check_cases.py

표준 라이브러리만 쓴다. 값이 맞는지는 보지 않는다(값은 사람이 책자와 대조한다).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from supplement import check_supplement  # noqa: E402

HERE = Path(__file__).resolve().parent
REQUIRED = [
    "id",
    "status",
    "review",
    "tax_year",
    "source",
    "kind",
    "groups",
    "question",
    "inputs",
    "expected",
    "notes",
]
GROUPS = {"basic_flow", "dependents", "child", "medical", "education", "card"}
KINDS = {"household", "item"}
STATUSES = {"draft", "confirmed"}


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
    pages = src.get("printed_pages") if isinstance(src, dict) else None
    if not (isinstance(src, dict) and src.get("book") and src.get("title")):
        errs.append("source에 book, title 필요")
    if not (isinstance(pages, list) and pages and all(isinstance(p, int) for p in pages)):
        errs.append("source.printed_pages는 정수 목록")
        pages = []
    if case["kind"] not in KINDS:
        errs.append(f"kind는 {sorted(KINDS)} 중 하나: {case['kind']}")
    if not case["groups"] or not set(case["groups"]) <= GROUPS:
        errs.append(f"groups는 {sorted(GROUPS)}의 부분집합: {case['groups']}")
    if not isinstance(case["expected"], list) or not case["expected"]:
        errs.append("expected는 비지 않은 목록")
    else:
        for i, exp in enumerate(case["expected"]):
            for key in ("stage", "value", "page", "booklet_text"):
                if key not in exp:
                    errs.append(f"expected[{i}]에 {key} 없음")
            if "value" in exp and not isinstance(exp["value"], (int, bool)):
                errs.append(f"expected[{i}].value는 정수(원) 또는 true/false: {exp['value']!r}")
            if "page" in exp and exp["page"] not in pages:
                errs.append(f"expected[{i}].page {exp['page']}가 source.printed_pages에 없음")
    if not isinstance(case["notes"], list):
        errs.append("notes는 목록")
    errs += check_supplement(case)
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
