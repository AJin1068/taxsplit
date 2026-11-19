"""가상 가구 생성 범위(PR 7 [계획] 표).

세법 숫자(공제 요건·한도·공제율)는 넣지 않는다. 가구를 만들 뿐 공제를 계산하지 않는다.
범위는 v1 대상(맞벌이 근로소득자)에 맞게 개발이 정한 값이다. 바꾸면 PR 표도 같이 고친다.
"""

# 귀속연도. 나이 → 출생연도 바꿀 때만 쓴다
YEAR = 2025

# 총급여: 2,000만~1억5,000만원, 1만원 단위
GROSS_MIN = 20_000_000
GROSS_MAX = 150_000_000
GROSS_UNIT = 10_000

# 지출·소득 금액은 1,000원 단위로 고른다
AMOUNT_UNIT = 1_000

# 부부 본인 나이
WORKER_AGE = (25, 65)

# 부양가족: 자녀 0~3명, 부모 0~2명, 합계 최대 4명
CHILDREN_MAX = 3
PARENTS_MAX = 2
DEPENDENTS_MAX = 4
CHILD_AGE = (0, 25)
PARENT_AGE = (55, 90)

# 부양가족 소득: 70%는 0원, 30%는 0~1,500만원.
# 30% 중 절반은 "근로소득만 있음"(총급여로 적음), 절반은 소득금액으로 적는다
NO_INCOME_RATIO = 0.7
INCOME_MAX = 15_000_000
WAGE_ONLY_RATIO = 0.5

# 장애인 비율(부양가족 한 명마다)
DISABLED_RATIO = 0.05

# 의료비: 사람(본인·부양가족)마다 0~1,000만원
MEDICAL_MAX = 10_000_000

# 교육비: 자녀마다 0~1,200만원, 본인은 10%만 0~1,000만원(대학)
CHILD_EDUCATION_MAX = 12_000_000
SELF_EDUCATION_RATIO = 0.1
SELF_EDUCATION_MAX = 10_000_000
# 자녀 나이로 과정을 정한다(세법 숫자가 아니라 학제). 이 나이 이하면 그 과정
PRESCHOOL_MAX_AGE = 6
SCHOOL_MAX_AGE = 18

# 카드: 총급여의 0~70%를 결제 수단 다섯 가지로 나눈다
CARD_GROSS_RATIO_MAX = 0.7
CARD_KINDS = ("credit", "cash_debit", "culture", "market", "transit")

# 국민연금·건강·고용보험료 합계: 총급여의 0~10%를 셋으로 나눈다
INSURANCE_GROSS_RATIO_MAX = 0.1
