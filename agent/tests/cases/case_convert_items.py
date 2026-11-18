"""사례의 의료비·교육비·카드 지출 → 엔진 입력 변환(테스트 쪽에만 둔다).

엔진은 "공제 대상인 지출"만 받는다(Issue #14 [계획] 정할 것 2). 그래서 책자 풀이가
"대상 아님"으로 뺀 지출은 여기서 빼고, 왜 뺐는지 옆에 적는다.
"""

from taxsplit.engine import CardUsage, EducationExpense, MedicalExpense, OutOfScopeItem
from taxsplit.engine.models_items import SELF

# 책자 풀이가 공제 대상에서 뺀 지출(사례 파일 notes·풀이 문장 근거)
NOT_ELIGIBLE_ITEMS = {
    # p185 notes: 초등학생 학원·체육시설 수강료는 대상 아님
    "학원 및 체육시설 수강료",
    # p212 notes(교육비 세부): 학원비와 본인 대학원(비과세학자금)은 대상 아님
    "학원수강료",
    "대학원(박사과정)",
    # p212 의료비 풀이 ③ 본인 등 180만원 = 입원치료비 130만 + 안경 50만. 건강증진 보약은 빠짐
    "보약(건강증진)",
}

_MEDICAL_ITEMS = {
    "난임시술비": "infertility",
    "산후조리원비용": "postnatal_care",
    "시력교정용안경": "glasses",
}
_EDUCATION_ITEMS = {"교복구입비": "uniform", "체험학습비": "field_trip"}
# 카드 사례의 "includes" 이름 → CardUsage 칸
_INCLUDES = {"public_transport": "transit", "traditional_market": "market"}


def _who(name: str) -> str:
    return SELF if name in ("worker", "self") else name


def medical_expenses(rows: list[dict]) -> tuple[MedicalExpense, ...]:
    """국세청 사례 expenses 줄 → 의료비 입력. for 이름이 그대로 부양가족 이름이 된다."""
    out = []
    for row in rows:
        if row.get("category", "medical") != "medical" or row["item"] in NOT_ELIGIBLE_ITEMS:
            continue
        item = _MEDICAL_ITEMS.get(row["item"], "general")
        out.append(MedicalExpense(for_name=_who(row["for"]), item=item, amount=row["amount"]))
    return tuple(out)


def education_expenses(rows: list[dict], levels: dict[str, str]) -> tuple[EducationExpense, ...]:
    """국세청 사례 expenses 줄 → 교육비 입력. levels = 부양가족 이름 → 교육 과정."""
    out = []
    for row in rows:
        if row.get("category", "education") != "education" or row["item"] in NOT_ELIGIBLE_ITEMS:
            continue
        who = _who(row["for"])
        item = _EDUCATION_ITEMS.get(row["item"], "general")
        out.append(
            EducationExpense(for_name=who, level=levels[who], item=item, amount=row["amount"])
        )
    return tuple(out)


def nts_card(usage: dict) -> tuple[CardUsage, ...]:
    """국세청 사례 card_usage(결제 수단별 total + includes) → 칸이 겹치지 않는 사용금액."""
    f = dict.fromkeys(
        ("credit", "cash_debit", "culture_credit", "culture_cash_debit", "market", "transit"), 0
    )
    for method, key in (
        ("credit_card", "credit"),
        ("cash_receipt", "cash_debit"),
        ("debit_card", "cash_debit"),
    ):
        row = usage.get(method)
        if not row:
            continue
        includes = row.get("includes", {})
        f[key] += row["total"] - sum(includes.values())
        for name, amount in includes.items():
            target = _INCLUDES.get(name) or f"culture_{key}"
            f[target] += amount
    assert sum(f.values()) == usage["total"]
    return (CardUsage(**f),)


def hometax_card(card: dict) -> tuple[CardUsage, ...]:
    """홈택스 입력 card(credit, debit, cash_receipt) → 사용금액. 전통시장 등은 넣지 않았다."""
    cash = card.get("debit", 0) + card.get("cash_receipt", 0)
    return (CardUsage(credit=card.get("credit", 0), cash_debit=cash),)


def hometax_spending(me: dict, rows: dict[str, dict]) -> dict:
    """홈택스 입력의 의료비·교육비를 그 사람이 공제받는 부양가족 이름에 붙인다.

    rows = 이 사람이 기본공제 받는 부양가족 이름 → 가족 표의 줄.
    """
    medical = []
    for amount in me.get("medical", {}).values():
        name = next(n for n, r in rows.items() if r.get("medical") == amount)
        medical.append(MedicalExpense(for_name=name, amount=amount))
    education = []
    levels = {"preschool": "preschool", "elementary_to_high": "school"}
    for key, amount in me.get("education", {}).items():
        name = next(n for n, r in rows.items() if r.get("education", {}).get("amount") == amount)
        education.append(EducationExpense(for_name=name, level=levels[key], amount=amount))
    return {
        "medical": tuple(medical),
        "education": tuple(education),
        "card_usage": hometax_card(me.get("card", {})),
    }


# 5그룹 밖 단계 값을 엔진 입력으로 옮긴다(Issue #14 정해진 결정). 채점하지 않는다
# 단계 이름 → (이름, kind, category, 종합한도 대상)
OUT_OF_SCOPE_STAGES = {
    "housing_fund_deduction": ("주택자금", "income_deduction", "special_income_deduction", True),
    "pension_account_credit": ("연금계좌", "tax_credit", "other", False),
    "insurance_credit": ("보장성보험료", "tax_credit", "special_tax_credit", False),
    "donation_credit": ("기부금", "tax_credit", "special_tax_credit", False),
}


def nts_out_of_scope(case: dict) -> tuple[OutOfScopeItem, ...]:
    out = []
    for e in case["expected"]:
        if e["stage"] in OUT_OF_SCOPE_STAGES:
            name, kind, category, combined = OUT_OF_SCOPE_STAGES[e["stage"]]
            out.append(
                OutOfScopeItem(
                    name=name,
                    kind=kind,
                    category=category,
                    amount=e["value"],
                    in_combined_limit=combined,
                )
            )
    return tuple(out)
