# eval

채점 규칙, 채점 코드, 정답 데이터, 국세청 계산 사례를 두는 곳입니다.

- 이 폴더는 개발 PR에서 고칠 수 없습니다. CI(`eval-guard`)가 `eval/`로 시작하지 않는 브랜치의 PR이 이 폴더를 바꾸면 실패시킵니다.
- 이 폴더를 바꾸려면 `eval/<설명>` 브랜치로 별도 PR을 엽니다. 처리 코드 변경과 섞지 않습니다.
- 정답 데이터는 `status: draft`로 시작하고, 사람이 검수한 뒤 `confirmed`로 바꿉니다. 채점에는 `confirmed`만 씁니다.
- 홀드아웃 시나리오는 이 레포에 두지 않습니다.

## 보충 입력 (`supplement`)

국세청 「2025년 원천징수의무자를 위한 연말정산 신고안내」 사례는 문서 문장을 그대로 옮겨서, 계산기에 넣으려면 필요한 값이 빠져 있는 경우가 있습니다(예: "60세 이상"으로만 적힌 부모 나이, 본인 성별·출생연도). 홈택스 사례도 입력표에 생년이 없습니다. 이런 값을 테스트 코드가 알아서 채우면 정답 데이터의 일부를 개발이 만든 셈이 되므로, 채운 값은 사례 파일의 `supplement` 칸에 적고 사람이 검수합니다.

- 문서에서 옮긴 `inputs`는 그대로 둡니다. `supplement`는 `inputs`에 **없는 칸만 더합니다**(있는 값을 덮어쓰면 형식 검사가 실패).
- 형식:

  ```jsonc
  "supplement": {
    "status": "draft",                          // draft | confirmed. 사례 status와 따로 검수
    "review": {"reviewer": null, "date": null},
    "values": [
      {
        "path": "/family/4/age",                // inputs 안 위치 (JSON Pointer, RFC 6901)
        "value": 60,
        "kind": "not_in_source",                // not_in_source: 문서에 없어 고른 값
                                                 // implied_by_source: 문서의 다른 문장·풀이에서 추론한 값
        "reason": "왜 이 값을 골랐나",
        "effect": "비교하는 단계에 영향이 없는 이유 (규칙표 규칙 ID로)"
      }
    ]
  }
  ```

- 값을 고르는 기준: 문서 범위("60세 이상")를 만족하는 가장 가까운 값, 또는 비교하는 단계에 영향을 주지 않는 값. 영향이 없는 이유는 규칙표(`agent/src/taxsplit/rules/rules_2025.toml`) 규칙 ID로 적습니다.
- 문서가 언급하지 않은 장애인 여부는 `false`로 읽습니다(보충 칸에 따로 적지 않음).
- 테스트는 `supplement.status`가 `confirmed`일 때만 보충 값을 씁니다. 사례의 `expected`(정답)는 바꾸지 않으므로 사례 `status`는 그대로입니다.
- 계산 엔진 처리 코드는 사례 파일을 읽지 않습니다. 테스트 쪽 변환 코드가 `inputs`와 `supplement`를 합쳐 엔진 입력으로 옮깁니다.
- 형식 검사는 각 폴더의 `check_cases.py`가 `cases/supplement.py`를 불러 함께 합니다.

## 공제 대상 여부 (`eligibility`)

사례의 의료비·교육비 지출 줄마다 "문서 풀이가 이 지출을 공제 대상으로 셌나"를 근거와 함께 적습니다. 예를 들어 국세청 「2025년 원천징수의무자를 위한 연말정산 신고안내」 종합사례에는 보약 150만원이 지출로 나오지만, 풀이(인쇄 218쪽, PDF 236쪽)는 "건강증진을 위한 보약구입비는 공제대상 아님"이라며 뺍니다. 이런 판단을 테스트 코드가 정답 숫자를 보고 짐작하지 않도록, 사례 파일이 갖고 사람이 검수합니다.

- 문서에서 옮긴 `inputs`는 그대로 두고, 지출 줄을 경로로 가리킵니다.
- 형식:

  ```jsonc
  "eligibility": {
    "status": "draft",                          // draft | confirmed. 사례 status와 따로 검수
    "review": {"reviewer": null, "date": null, "scope": null},
    "rows": [
      {
        "path": "/expenses/6",                  // inputs 안 지출 줄 (JSON Pointer)
        "deductible": false,                    // 문서 풀이가 공제 대상으로 셌나
        "filtered_by": "input",                 // deductible이 false일 때만. 아래 설명
        "page": 218,                            // 국세청 사례만. source.printed_pages 안의 인쇄 쪽
        "text": "※ 건강증진을 위한 보약구입비는 공제대상 아님"  // 원문 문구 또는 근거
      }
    ]
  }
  ```

- `filtered_by`:
  - `input`: 지출 종류 자체가 대상이 아닙니다. 테스트는 이 줄을 엔진에 넣지 않습니다(보약, 초중고 학원비, 비과세 학자금). 엔진은 공제 대상인 지출만 받기 때문입니다.
  - `engine`: 엔진에 넣으면 규칙표 규칙이 0으로 만듭니다(예: 부양가족의 대학원 교육비). 테스트는 이 줄도 엔진에 넣어 엔진이 0을 내는지 봅니다.
- 한도에 걸려 일부만 들어가는 줄(안경 50만원, 산후조리원 200만원, 체험학습 30만원 등)은 `deductible: true`입니다. 잘리는 것은 엔진 규칙입니다.
- 홈택스 사례는 쪽이 없어서 `page`를 쓰지 않고, `text`에 "홈택스 입력값"이라는 근거를 적습니다. 맞벌이 배분 규칙(누가 냈나)으로 공제가 안 되는 것은 지출 종류의 문제가 아니므로 여기서 거르지 않습니다.
- **빠지면 실패합니다.** 의료비·교육비 지출 줄(국세청 사례 `inputs.expenses` 중 category가 medical·education이거나 없는 줄, 홈택스 사례 `inputs.family`의 가족별 `medical`·`education`)이 하나라도 `rows`에 없으면 형식 검사가 실패합니다. 카드는 사례에 결제 수단별 합계만 있어서 대상이 아닙니다.
- 테스트는 `eligibility.status`가 `confirmed`일 때만 이 칸을 씁니다.
- 형식 검사는 각 폴더의 `check_cases.py`가 `cases/eligibility.py`를 불러 함께 합니다. 검사 자체의 테스트는 `python3 eval/cases/test_eligibility.py`입니다.
