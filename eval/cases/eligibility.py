"""사례 파일의 `eligibility`(지출마다 공제 대상인가) 칸 형식 검사.

두 폴더의 check_cases.py가 같이 쓴다.

의료비·교육비 지출 줄마다 "문서 풀이가 이 지출을 공제 대상으로 셌나"를 근거와 함께 적는다.
한 줄이라도 빠지면 실패해서, 문서에서 옮길 때 "대상 아님" 한 줄을 놓치는 일을 막는다.
규칙은 README "공제 대상 여부" 절.
"""

STATUSES = {"draft", "confirmed"}
FILTERS = {"input", "engine"}
ROW_KEYS = {"path", "deductible", "filtered_by", "page", "text"}
REQUIRED_ROW_KEYS = {"path", "deductible", "text"}
GROUP_CATEGORIES = {"medical", "education"}


def _get(doc, path: str):
    """JSON Pointer(RFC 6901, '~' 이스케이프 없음)로 값을 찾는다. 없으면 KeyError."""
    cur = doc
    for part in path[1:].split("/"):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            raise KeyError(path)
    return cur


def expense_paths(case: dict) -> list[str]:
    """공제 대상 여부를 꼭 적어야 하는 지출 줄의 `inputs` 안 경로.

    - 국세청 사례: `inputs.expenses`의 줄 중 category가 medical·education이거나 category가 없는 줄
      (항목 사례는 category 없이 그 사례 그룹의 지출만 담는다).
    - 홈택스 사례: `inputs.family`의 가족(목록이면 한 사람씩)마다 `education`·`medical`.
    카드는 사례에 결제 수단별 합계만 있고 줄이 없어서 대상이 아니다.
    """
    inputs = case.get("inputs", {})
    out: list[str] = []
    for i, row in enumerate(inputs.get("expenses", []) or []):
        if isinstance(row, dict) and ("category" not in row or row["category"] in GROUP_CATEGORIES):
            out.append(f"/expenses/{i}")
    family = inputs.get("family")
    if isinstance(family, dict):
        for name, member in family.items():
            people = enumerate(member) if isinstance(member, list) else [(None, member)]
            for i, person in people:
                base = f"/family/{name}" + ("" if i is None else f"/{i}")
                for key in ("education", "medical"):
                    if isinstance(person, dict) and key in person:
                        out.append(f"{base}/{key}")
    return out


def check_eligibility(case: dict) -> list[str]:
    need = expense_paths(case)
    if "eligibility" not in case:
        return (
            [f"eligibility 칸 없음(지출 줄 {len(need)}개의 공제 대상 여부를 적어야 함)"]
            if need
            else []
        )
    errs: list[str] = []
    el = case["eligibility"]
    if not isinstance(el, dict):
        return ["eligibility는 객체"]
    if el.get("status") not in STATUSES:
        errs.append(f"eligibility.status는 {sorted(STATUSES)} 중 하나: {el.get('status')}")
    review = el.get("review")
    if not isinstance(review, dict) or not {"reviewer", "date"} <= review.keys():
        errs.append("eligibility.review에 reviewer, date 칸 필요")
    elif el.get("status") == "confirmed" and not (review["reviewer"] and review["date"]):
        errs.append("eligibility가 confirmed면 review.reviewer와 review.date를 채워야 함")
    rows = el.get("rows")
    if not isinstance(rows, list):
        return errs + ["eligibility.rows는 목록"]
    src = case.get("source", {})
    pages = src.get("printed_pages") if isinstance(src, dict) else None
    seen: set[str] = set()
    for i, row in enumerate(rows):
        tag = f"eligibility.rows[{i}]"
        if (
            not isinstance(row, dict)
            or not REQUIRED_ROW_KEYS <= row.keys()
            or not row.keys() <= ROW_KEYS
        ):
            errs.append(f"{tag} 칸은 {sorted(REQUIRED_ROW_KEYS)} 필수, 그 밖엔 filtered_by·page만")
            continue
        path = row["path"]
        if not (isinstance(path, str) and path.startswith("/")):
            errs.append(f"{tag}.path는 '/'로 시작하는 inputs 안 경로: {path!r}")
            continue
        if path in seen:
            errs.append(f"{tag}.path 중복: {path}")
        seen.add(path)
        try:
            _get(case.get("inputs", {}), path)
        except KeyError:
            errs.append(f"{tag}.path {path}가 inputs에 없음")
        if path not in need:
            errs.append(f"{tag}.path {path}는 의료비·교육비 지출 줄이 아님")
        if not isinstance(row["deductible"], bool):
            errs.append(f"{tag}.deductible은 true/false")
        elif row["deductible"] is False and row.get("filtered_by") not in FILTERS:
            errs.append(f"{tag}: 공제 대상 아님이면 filtered_by는 {sorted(FILTERS)} 중 하나")
        elif row["deductible"] is True and "filtered_by" in row:
            errs.append(f"{tag}: 공제 대상이면 filtered_by를 쓰지 않음")
        if not (isinstance(row["text"], str) and row["text"].strip()):
            errs.append(f"{tag}.text는 비지 않은 글(원문 문구 또는 근거)")
        if pages:
            if row.get("page") not in pages:
                errs.append(f"{tag}.page {row.get('page')}가 source.printed_pages에 없음")
        elif "page" in row:
            errs.append(f"{tag}.page: 쪽이 없는 사례(홈택스)는 page를 쓰지 않음")
    for path in need:
        if path not in seen:
            errs.append(f"eligibility.rows에 지출 줄 {path}가 없음(공제 대상 여부를 적어야 함)")
    return errs
