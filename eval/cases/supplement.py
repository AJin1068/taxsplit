"""사례 파일의 `supplement`(보충 입력) 칸 형식 검사. 두 폴더의 check_cases.py가 같이 쓴다.

보충 입력은 문서(국세청 신고안내, 홈택스 입력표)에 없어서 계산기에 넣으려면 채워야 하는 값이다.
문서에서 옮긴 `inputs`는 그대로 두고, 채운 값은 여기에만 적는다. 규칙은 README "보충 입력" 절.
"""

KINDS = {"not_in_source", "implied_by_source"}
STATUSES = {"draft", "confirmed"}
ENTRY_KEYS = {"path", "value", "kind", "reason", "effect"}


def _resolve(doc, parts):
    """JSON Pointer 조각을 따라간다. 끝까지 있으면 True."""
    cur = doc
    for part in parts:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return False
    return True


def check_supplement(case: dict) -> list[str]:
    if "supplement" not in case:
        return []
    errs: list[str] = []
    sup = case["supplement"]
    if not isinstance(sup, dict):
        return ["supplement는 객체"]
    if sup.get("status") not in STATUSES:
        errs.append(f"supplement.status는 {sorted(STATUSES)} 중 하나: {sup.get('status')}")
    review = sup.get("review")
    if not isinstance(review, dict) or not {"reviewer", "date"} <= review.keys():
        errs.append("supplement.review에 reviewer, date 칸 필요")
    elif sup.get("status") == "confirmed" and not (review["reviewer"] and review["date"]):
        errs.append("supplement가 confirmed면 review.reviewer와 review.date를 채워야 함")
    values = sup.get("values")
    if not isinstance(values, list) or not values:
        return errs + ["supplement.values는 비지 않은 목록"]
    seen: set[str] = set()
    for i, ent in enumerate(values):
        if not isinstance(ent, dict) or set(ent) != ENTRY_KEYS:
            errs.append(f"supplement.values[{i}] 칸은 {sorted(ENTRY_KEYS)}")
            continue
        path = ent["path"]
        if not (isinstance(path, str) and path.startswith("/") and len(path) > 1):
            errs.append(f"supplement.values[{i}].path는 '/'로 시작하는 inputs 안 경로: {path!r}")
            continue
        if path in seen:
            errs.append(f"supplement.values[{i}].path 중복: {path}")
        seen.add(path)
        # 문서에서 옮긴 값을 덮어쓰지 않는다: inputs에 이미 있는 경로면 실패
        if _resolve(case.get("inputs", {}), path[1:].split("/")):
            errs.append(f"supplement.values[{i}].path {path}는 inputs에 이미 있음(문서 값을 덮어쓸 수 없음)")
        if ent["kind"] not in KINDS:
            errs.append(f"supplement.values[{i}].kind는 {sorted(KINDS)} 중 하나: {ent['kind']}")
        for key in ("reason", "effect"):
            if not (isinstance(ent[key], str) and ent[key].strip()):
                errs.append(f"supplement.values[{i}].{key}는 비지 않은 글")
    return errs
