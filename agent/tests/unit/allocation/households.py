"""손으로 만든 가상 맞벌이 가구 5개(eval/ 사례의 값·이름을 쓰지 않음).

1 소득 비슷 + 자녀 둘 / 2 소득 차이 큼 + 양가 부모 / 3 의료비 문턱 근처
4 카드 문턱 근처 / 5 부양가족 없음(안 1개)
"""

from taxsplit.allocation import (
    CardSpend,
    Earner,
    EducationSpend,
    Household,
    MedicalSpend,
    Member,
)
from taxsplit.engine import Dependent


def earner(gross: int, sex: str, birth_year: int = 1988) -> Earner:
    # 보험료는 총급여에 대략 비례하는 값으로 둔다(국민연금 4.5%, 건강 3.5%, 고용 0.9%)
    return Earner(
        gross_salary=gross,
        sex=sex,
        birth_year=birth_year,
        national_pension=gross * 45 // 1000,
        health_insurance=gross * 35 // 1000,
        employment_insurance=gross * 9 // 1000,
    )


def child(name: str, birth_year: int) -> Member:
    return Member(dependent=Dependent(name=name, relation="child", birth_year=birth_year))


def parent(name: str, birth_year: int, family_of: str, income: int = 0) -> Member:
    dep = Dependent(
        name=name, relation="lineal_ascendant", birth_year=birth_year, income_amount=income
    )
    return Member(dependent=dep, family_of=family_of)


def own_cards(husband: int, wife: int) -> tuple[CardSpend, ...]:
    return (CardSpend(user="husband", credit=husband), CardSpend(user="wife", credit=wife))


# 1) 소득 비슷 + 자녀 둘. 작은아이 의료비는 아내가 냄(아내 총급여 3% 150만원 넘음),
#    큰아이 교육비는 남편이 냄
SIMILAR_WITH_KIDS = Household(
    husband=earner(52_000_000, "male"),
    wife=earner(50_000_000, "female"),
    members=(child("큰아이", 2015), child("작은아이", 2019)),
    medical=(MedicalSpend(payer="wife", for_whom="작은아이", amount=2_500_000),),
    education=(EducationSpend(payer="husband", for_whom="큰아이", level="school", amount=600_000),),
    cards=own_cards(16_000_000, 15_000_000),
)

# 2) 소득 차이 큼 + 양가 부모. 아내 어머니 의료비는 아내가 냄
WIDE_GAP_PARENTS = Household(
    husband=earner(92_000_000, "male", 1980),
    wife=earner(31_000_000, "female", 1982),
    members=(parent("남편아버지", 1952, "husband"), parent("아내어머니", 1959, "wife")),
    medical=(MedicalSpend(payer="wife", for_whom="아내어머니", amount=3_000_000),),
    cards=own_cards(30_000_000, 11_000_000),
)

# 3) 의료비 문턱 근처: 남편이 낸 어머니 의료비가 남편 총급여 3%(180만원)를 조금 넘음
MEDICAL_NEAR_THRESHOLD = Household(
    husband=earner(60_000_000, "male", 1979),
    wife=earner(40_000_000, "female", 1981),
    members=(parent("시어머니", 1956, "husband"), child("막내", 2022)),
    medical=(
        MedicalSpend(payer="husband", for_whom="시어머니", amount=1_850_000),
        MedicalSpend(payer="wife", for_whom="막내", amount=900_000),
    ),
    cards=own_cards(20_000_000, 14_000_000),
)

# 4) 카드 문턱 근처: 아내 카드가 아내 총급여 25%(1,200만원)를 조금 넘고, 자녀 카드 300만원
CARD_NEAR_THRESHOLD = Household(
    husband=earner(70_000_000, "male"),
    wife=earner(48_000_000, "female"),
    members=(child("중학생", 2012),),
    # 아내 카드 중 200만원은 남편 명의 가족카드를 아내가 쓴 것(쓴 사람 기준)
    cards=(
        CardSpend(user="husband", credit=15_500_000),
        CardSpend(user="wife", credit=10_500_000),
        CardSpend(user="wife", payer="husband", credit=2_000_000),
        CardSpend(user="중학생", payer="husband", cash_debit=3_000_000),
    ),
)

# 5) 부양가족 없음: 비교할 안이 하나뿐
NO_DEPENDENTS = Household(
    husband=earner(45_000_000, "male"),
    wife=earner(43_000_000, "female"),
    cards=own_cards(12_000_000, 13_000_000),
)

HOUSEHOLDS = {
    "1 소득 비슷+자녀": SIMILAR_WITH_KIDS,
    "2 소득 차이+양가 부모": WIDE_GAP_PARENTS,
    "3 의료비 문턱 근처": MEDICAL_NEAR_THRESHOLD,
    "4 카드 문턱 근처": CARD_NEAR_THRESHOLD,
    "5 부양가족 없음": NO_DEPENDENTS,
}
