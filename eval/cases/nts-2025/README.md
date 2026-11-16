# 국세청 2025 귀속 책자 사례 (PR 3a)

국세청 「2025년 원천징수의무자를 위한 연말정산 신고안내」(2025.12 발간, 정오표 2026.02.03)의 계산 사례를 사례당 JSON 파일 하나로 옮긴 것입니다. 계산 엔진(PR 4·5)의 바깥 정답입니다(정답 사슬 1단계, `docs/adr/0004-ground-truth-chain.md`).

- 값은 책자에 인쇄된 숫자를 그대로 옮겼습니다. 책자에 없는 값은 계산해서 채우지 않았습니다. 만원 단위 표기(예: 1,032만원)만 원 단위 정수(10320000)로 바꿨습니다.
- 쪽수는 **인쇄 쪽**입니다. PDF 쪽 = 인쇄 쪽 + 18 (예: 인쇄 95쪽 = PDF 113쪽).
- 책자 PDF는 레포에 넣지 않습니다(재배포 가능 여부 확인 필요). 원본은 프로젝트 파일 `taxsplit-docs/sources/`에 있습니다.
- 전부 `status: draft`입니다. 사람이 책자와 대조한 뒤 `status: confirmed`로 바꾸고 `review.reviewer`, `review.date`를 채웁니다. PR 4·5 테스트는 `confirmed`만 씁니다.

## 사례 목록

| 파일 | 인쇄 쪽 | 종류 | 그룹 | 마지막 기대값 단계 | 책자 답 | status |
| --- | --- | --- | --- | --- | --- | --- |
| `household-p212-comprehensive.json` | 212~219 | 가구 | 기본 흐름·부양가족·자녀·의료비·교육비·카드 (+5그룹 밖) | `determined_tax` 240,232원 / `refund_or_payment` △759,768원 | 결정세액 240,232원 | draft |
| `item-p095-earned-income.json` | 95 | 항목 | 기본 흐름 | `earned_income_deduction`, `earned_income_amount` | 1,032만원 / 2,348만원 | draft |
| `item-p162-earned-income-credit-1.json` | 162 | 항목 | 기본 흐름 | `earned_income_credit` | 49만 5천원 | draft |
| `item-p162-earned-income-credit-2.json` | 162 | 항목 | 기본 흐름 | `earned_income_credit` | 66만원 | draft |
| `item-p097-basic-deduction.json` | 97 | 항목 | 부양가족 | `basic_deduction_total` | 1,050만원 | draft |
| `item-p099-disabled-child.json` | 99 | 항목 | 부양가족 | `basic_deduction_person`, `additional_deduction_disabled` | 150만원 / 200만원 | draft |
| `item-p100-marriage-death.json` | 100 | 항목 | 부양가족 | 문1 `spouse_basic_deduction_eligible`, 문2 `personal_deduction_person_total` | 가능 / 250만원 | draft |
| `item-p177-medical.json` | 177 | 항목 | 의료비 | `medical_credit` | 1,335천원 | draft |
| `item-p185-education.json` | 185 | 항목 | 교육비 | `education_credit` | 4,305,000원 | draft |
| `item-p137-card.json` | 137~138 | 항목 | 카드 | `card_deduction` | 530만원 | draft |

합계 10건 (가구 1 + 항목 9).

## 그룹별 건수

| 그룹 | 가구 사례 | 항목 사례 | 합계 |
| --- | --- | --- | --- |
| 기본 흐름 (`basic_flow`) | 1 | 3 (p95, p162 ①②) | 4 |
| 부양가족 (`dependents`) | 1 | 3 (p97, p99, p100) | 4 |
| 자녀 (`child`) | 1 | 0 | 1 |
| 의료비 (`medical`) | 1 | 1 (p177) | 2 |
| 교육비 (`education`) | 1 | 1 (p185) | 2 |
| 카드 (`card`) | 1 | 1 (p137~138) | 2 |

자녀세액공제만 다룬 항목 사례는 책자에 없습니다. 자녀 그룹은 가구 사례 1건뿐이라 PR 3c(홈택스 모의계산)에서 보완합니다.

## 파일 형식

```jsonc
{
  "id": "nts2025-p177-medical",       // 고유 id
  "status": "draft",                  // draft | confirmed
  "review": {"reviewer": null, "date": null},  // confirmed로 바꿀 때 채움
  "tax_year": 2025,
  "source": {"book": "...", "printed_pages": [177], "title": "책자의 사례 제목"},
  "kind": "item",                     // household(가구 전체) | item(항목)
  "groups": ["medical"],              // basic_flow, dependents, child, medical, education, card
  "other_groups_in_case": [],         // (가구 사례만) 5그룹 밖 공제
  "question": "책자 질문 문장",
  "inputs": { ... },                  // 책자에 나온 입력값. 금액은 원 단위 정수
  "expected": [
    {"stage": "medical_credit", "value": 1335000, "page": 177, "booklet_text": "책자 식 그대로"}
  ],
  "notes": ["책자 이유 설명, 불일치, 애매한 곳"]
}
```

- `expected`는 책자 풀이에 나온 순서대로 적은 단계값 목록입니다. 각 칸은 **어느 단계의 값인지(`stage`)**, 값(`value`, 원 단위 정수 또는 true/false), 그 값이 인쇄된 쪽(`page`), 책자 식 원문(`booklet_text`)입니다. 한 사례에 질문이 둘이면 `sub_question`으로 나눕니다(p100).
- 음수는 환급입니다(`refund_or_payment` −759,768 = 책자 "△ 759,768원").
- `inputs`의 칸 이름은 이 폴더 안에서만 쓰는 이름입니다. 계산 엔진은 이 파일을 직접 읽지 않고, PR 4·5 테스트가 엔진 입력으로 옮겨 씁니다.

### 단계 이름 (`stage`)

| stage | 뜻 |
| --- | --- |
| `total_pay` | 급여 합계(비과세 포함) |
| `nontaxable_total` | 비과세 소계 |
| `gross_salary` | 총급여액 |
| `earned_income_deduction` | 근로소득공제 |
| `earned_income_amount` | 근로소득금액 |
| `basic_deduction_count` | 기본공제 인원 |
| `basic_deduction_total` | 기본공제 합계 |
| `basic_deduction_person` | 한 사람의 기본공제 |
| `additional_deduction_disabled` | 장애인 추가공제 |
| `additional_deduction_elderly` | 경로우대자 추가공제 |
| `personal_deduction_person_total` | 한 사람의 인적공제(기본+추가) |
| `spouse_basic_deduction_eligible` | 배우자 기본공제 가능 여부 (true/false) |
| `pension_insurance_deduction` | 연금보험료공제 (5그룹 밖) |
| `insurance_premium_deduction` | 건강보험료 등 보험료공제 (5그룹 밖) |
| `housing_fund_deduction` | 주택자금공제 (5그룹 밖) |
| `card_minimum_spend` | 카드 최저사용금액(총급여의 25%) |
| `card_part_credit` / `card_part_cash_debit` / `card_part_culture_sports` / `card_part_traditional_market` / `card_part_public_transport` | 카드 공제 ①~⑤ 부분값 |
| `card_minimum_spend_deduction` | ⑥ 최저사용금액에 해당하는 공제금액 |
| `card_deductible_before_limit` | 카드 공제 가능금액(①~⑤ − ⑥) |
| `card_limit` | 카드 총 공제한도 |
| `card_deduction` | 카드 소득공제액 |
| `comprehensive_limit_target` / `comprehensive_limit_excess` | 소득공제 종합한도 대상액 / 초과액 |
| `comprehensive_income_deduction` | 종합소득공제 (인적·연금보험료·특별소득공제) |
| `other_income_deduction` | 그밖의 소득공제 |
| `taxable_income` | 과세표준 |
| `computed_tax` | 산출세액 |
| `earned_income_credit_before_limit` / `earned_income_credit_limit` / `earned_income_credit` | 근로소득세액공제 한도 전 / 한도 / 공제액 |
| `child_credit_age8plus` / `child_credit_birth` / `child_credit` | 자녀세액공제 8세 이상분 / 출산·입양분 / 합계 |
| `pension_account_credit` | 연금계좌 세액공제 (5그룹 밖) |
| `insurance_credit` | 보험료 세액공제 (5그룹 밖) |
| `medical_threshold` | 의료비 문턱(총급여의 3%) |
| `medical_base_general` / `medical_base_special` / `medical_base_infertility` | 의료비 대상금액: 그 외 부양가족 / 본인·65세 이상·장애인 등 / 난임시술비 |
| `medical_credit_base` / `medical_credit` | 의료비 세액공제 대상금액 / 공제액 |
| `education_base_self` / `education_base_children` / `education_base_siblings` | 교육비 대상금액: 본인 / 자녀 / 형제자매 |
| `education_credit_base` / `education_credit` | 교육비 세액공제 대상금액 / 공제액 |
| `donation_credit` | 기부금 세액공제 (5그룹 밖) |
| `special_tax_credit_total` | 특별세액공제 합계 |
| `determined_tax` | 결정세액 |
| `refund_or_payment` | 환급(−)·납부(+) 세액 |

## 형식 검사

```bash
python3 eval/cases/nts-2025/check_cases.py
```

필수 칸, 값 타입, `confirmed`면 검수자·날짜가 있는지, `page`가 `printed_pages` 안에 있는지 봅니다. 값이 맞는지는 보지 않습니다(사람이 책자와 대조).

## 책자 안 불일치·확인 필요

| 쪽 | 내용 | 영향 |
| --- | --- | --- |
| p219 vs p215 | p219 기부금 풀이 ①에 "근로소득금액：54,660,000원", p215 근로소득금액은 52,380,000원 | 기부금 세액공제액·결정세액은 한도에 안 걸려 그대로. 가구 사례 `notes`에 적음 |
| p217 vs p164 | p217 자녀세액공제 괄호 "3명이상：55만원 + 2명초과 1명당 30만원", p164 표 "2명 초과하는 1명당 연 40만원(3명：95만원)" | 이 가구는 8세 이상 자녀 1명이라 영향 없음. 규칙표(PR 3b)·계산 엔진에서 어느 쪽인지 확인 필요 |
| p219 | 기부금 풀이 번호 ②가 두 번(정치자금, 고향사랑) | 인쇄상 번호 중복, 값 영향 없음 |
| p138 | 카드 총 공제한도 식의 대괄호 하나가 닫히지 않음 | 값 영향 없음 |
| p177 | 산후조리원비용 250만원이 풀이에 200만원으로 들어감(한도 문장은 풀이에 없음) | 값은 책자 그대로 |

## 정오표 (2026.02.03, 참고)

1. 컬러 페이지: 고향사랑기부금(조특법 제58조) 한도 연간 500만원 → 연간 2,000만원
2. p232 [별지 제74호의6서식] 신용카드 등 소득공제 신청서 서식의 계산식 구분란 수정

둘 다 옮긴 사례의 값에는 영향이 없습니다(가구 사례 고향사랑기부금 10만원, p232는 서식).

## 옮기지 않은 것

- p220~247: 같은 종합사례 가구의 소득·세액공제신고서, 근로소득 원천징수영수증 작성 예시(서식). 새 계산 사례가 아님
- p254: 수정 원천징수이행상황신고서 작성사례(회사 단위 서식, 직계존속 중복공제로 추가 납부 200,000원). 한 사람의 계산 풀이가 없음
- p264~267: 같은 가구의 경정청구 사례(종교단체기부금 100만원 누락). 기부금만 다뤄 5그룹 밖
- 사업·연금·종교인 소득 사례: 근로소득자가 아님
- 인쇄 82~221쪽의 다른 【문】 사례 8건: p93 외국인 단일세율, p128 벤처투자, p151 중소기업 취업자 감면, p166·p167 연금계좌, p172 보험료, p209 외국납부세액공제, p210 주택 관련. 모두 5그룹 밖
- 맞벌이 배분 정답: PR 6 이후 계산 엔진이 만든다
