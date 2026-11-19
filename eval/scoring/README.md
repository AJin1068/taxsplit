# 채점

평가 하네스의 채점 규칙과 채점 코드입니다. `eval/` 벽 안이라 개발 PR이 고칠 수 없습니다.

| 파일 | 내용 |
| --- | --- |
| `rules.md` | 채점 규칙(숫자마다 정의, 맞음·틀림 예시, 기준 수치 비교). 사람이 승인한 것 |
| `score.py` | 채점 코드. 표준 라이브러리만 쓰고 계산 엔진을 import하지 않음 |
| `test_score.py` | 채점 코드·시나리오 형식 테스트. `python3 eval/scoring/test_score.py` |

평가 하네스 실행기(`agent/src/taxsplit/harness/`, PR 11)는 `score.py`를 파일 경로로 불러 아래 함수를 씁니다.

| 함수 | 하는 일 |
| --- | --- |
| `load_scenarios(폴더)` | 시나리오를 읽고 형식을 검사한다. 틀리면 파일 이름과 이유를 담은 `ValueError` |
| `summarize(시나리오 목록, 실행 기록 목록)` | 대화마다 점수, 시나리오별·그룹별·전체 숫자 |
| `compare_to_baseline(지금 summarize 결과, 기준 summarize 결과)` | "떨어짐 / 같음 또는 좋아짐"과 비용 경고 |

## 실행 기록 형식

실행기가 대화 하나(시나리오 하나 × 반복 1번)를 돌린 뒤 남기는 JSON입니다. 채점 코드의 입력입니다.

```jsonc
{
  "scenario_id": "v0-01",
  "repeat": 1,                       // 몇 번째 반복(1부터)
  "ended": "answered",               // answered | stopped | error | max_turns
  "turns": 4,                        // 사용자 턴 수
  "transcript": [{"role": "user", "text": "..."}, {"role": "assistant", "text": "..."}],
  "revealed": ["f2", "f4"],          // 가상 사용자가 알려 준 사실 id(턴마다 모은 것, 먼저 말해 준 것도 포함)
  "tool_calls": [                    // 채팅 API done 이벤트의 tool_calls를 턴 순서대로 이은 것
    {"tool": "check_eligibility", "status": "ok", "errors": []}
  ],
  "final": {                         // 마지막으로 성공한 배분 비교(채팅 API allocation 이벤트). 없으면 null
    "assignment": {"어머님": "husband"},   // allocation.best.assignment (화면에 보여 준 최적안)
    "members": [{"name": "어머님", "relation": "lineal_ascendant", "birth_year": 1958}]
  },
  "cost": {"main_agent_usd": 0.12, "sim_user_usd": 0.01, "judge_usd": null},  // 모르면 null
  "judge": {"consistent": true, "reason": "..."}   // GPT 채점(--judge)을 안 했으면 null
}
```

- `final.members`는 그 배분 비교에 쓴 부양가족 전부(요건이 안 되는 사람 포함)입니다.
- `cost`의 값을 하나라도 모르면(`null`) 대화당 비용은 "알 수 없음"(`null`)으로 나옵니다.
