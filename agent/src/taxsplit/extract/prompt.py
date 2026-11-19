"""AI 정리 단계의 지시문 만들기.

"공제 대상이 아닌 지출"·"빼고 계산하는 금액" 목록은 코드에 쓰지 않고 규칙표
(`*.excluded_spending` 규칙의 items)에서 읽어 넣는다(설계 원칙 5).
"""

import json

from taxsplit.extract.models import GROUP_LABELS, ExtractedDoc
from taxsplit.rules.loader import EXCLUDED_SUFFIX, Rule, load_rules

# 규칙표 항목 종류 → AI에게 줄 표시 방법
_MARK_GUIDE = {
    "exclude": "mark를 exclude로",
    "subtract": "mark를 subtract로",
    "condition": "mark는 none으로 두고 notes에 '확인 필요: <줄 내용>'을 한 줄 남김",
}
# 그룹 규칙표 이름 → 추출 그룹(규칙표에는 insurance·other 그룹이 없다)
_RULE_TO_EXTRACT_GROUP = {"medical": "medical", "education": "education", "card": "card"}


def excluded_lines(rules: dict[str, Rule]) -> list[str]:
    """규칙표의 '공제 대상이 아닌 지출' 항목을 지시문 줄로."""
    lines = []
    for rule in rules.values():
        if not rule.id.endswith(EXCLUDED_SUFFIX):
            continue
        group = _RULE_TO_EXTRACT_GROUP.get(rule.group, rule.group)
        label = GROUP_LABELS.get(group, group)
        for item in rule.items:
            lines.append(f"- [{label}] {item.name} → {_MARK_GUIDE[item.kind]}")
    return lines


def build_system_prompt(rules: dict[str, Rule] | None = None) -> str:
    """지시문. rules를 안 주면 2025 규칙표를 읽는다(작년 PDF도 표시는 올해 목록으로 한다)."""
    rules = rules if rules is not None else load_rules(2025)
    schema = json.dumps(ExtractedDoc.model_json_schema(), ensure_ascii=False)
    groups = "\n".join(f"- {key}: {label}" for key, label in GROUP_LABELS.items())
    excluded = "\n".join(excluded_lines(rules))
    return f"""너는 연말정산 간소화 PDF에서 뽑은 글자를 정해진 JSON 형식으로 옮기는 정리기다.
계산하지 말고, PDF에 적힌 것만 옮긴다.

규칙:
1. 답은 JSON 객체 하나만 쓴다. 설명 글이나 ``` 를 붙이지 않는다.
2. 표의 한 줄(대상자 한 명의 한 지출)을 items의 항목 하나로 옮긴다.
   같은 대상자·같은 금액 줄이 여러 번 있으면 모두 따로 옮긴다(합치지 않는다).
   금액이 0원인 줄도 옮긴다.
3. amount는 원 단위 정수다(쉼표·'원'을 뺀다). 금액을 더하거나 고치지 않는다.
4. group은 아래 중 하나다. 공제 4그룹에 안 맞는 줄(기부금·연금저축 등)은 other다.
{groups}
5. kind에는 PDF에 적힌 세부 종류를 짧게 쓴다(예: 신용카드, 직불·선불카드, 현금영수증,
   전통시장, 대중교통, 문화체육, 취학 전, 초중고, 대학, 장애인특수, 일반, 안경,
   산후조리원, 난임, 실손보험금 수령, 국민연금, 건강보험).
6. person_birth는 PDF에 생년이나 생년월일 앞자리가 있으면 그대로, 없으면 null.
7. source_text에는 그 항목을 뽑은 줄의 글자를 그대로 쓴다.
8. totals에는 PDF에 그룹 합계가 적혀 있을 때만 넣는다. 없으면 빈 목록이다.
   mark가 subtract인 줄은 그룹 합계에 들지 않는다.
9. tax_year는 PDF에 적힌 귀속연도 그대로다. prior_year는 false로 둔다(코드가 채운다).
10. 표가 쪽에서 끊겨 이어지면 이어서 한 표로 읽는다.
11. 아래 목록에 해당하는 줄은 지우지 말고 옮긴 뒤 표시한다. 목록에 없으면 mark는 none이다.
{excluded}

JSON 형식(JSON Schema):
{schema}"""


def build_user_message(pdf_text: str) -> str:
    return f"다음은 간소화 PDF에서 뽑은 글자다. JSON으로 정리해라.\n\n{pdf_text}"


def build_retry_message(errors: list[str]) -> str:
    reasons = "\n".join(f"- {e}" for e in errors)
    return f"방금 답이 검사에 떨어졌다. 아래 문제를 고친 JSON 객체 하나만 다시 써라.\n{reasons}"
