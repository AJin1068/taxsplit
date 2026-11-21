# ADR-0010. 상담 모델을 Claude Haiku 5.5로 고정한다

- 상태: 승인됨
- 날짜: 2026-11-21
- 결정자: 서아진
- 일부 대체: [ADR-0006](0006-model-roles.md)의 "메인 에이전트는 Claude Sonnet 5.5"와 "시나리오④로 메인 모델 선택을 숫자로 확인한다"

## 맥락

실서비스 공개(11/27)부터 상담(메인 대화) 비용이 실제로 나간다. ADR-0006은 메인 에이전트와 서비스 안 검증 에이전트를 Claude Sonnet 5.5로 두었다. 100만 토큰당 가격(넣는 글자 / 받는 글자, 2026-11-20 확인)은 다음과 같다.

| 모델 | 넣는 글자 | 받는 글자 |
| --- | --- | --- |
| Claude Sonnet 5.5 | $2 | $10 |
| Claude Haiku 5.5 (질문 하나 10만 토큰 이하) | $0.10 | $0.50 |
| Claude Haiku 5.5 (10만 토큰 넘음) | $0.50 | $2.50 |

같은 대화면 Haiku가 약 20배 싸다.

## 결정

- 상담(메인 대화, `llm_model_main_agent`)과 서비스 안 검증 에이전트(`llm_model_verifier`)는 Claude Haiku 5.5를 쓴다 (2026-11-21 사용자 결정, 이유는 비용).
- 코드 기본값(`agent/src/taxsplit/core/config.py`의 `DEFAULT_MODEL`)과 `.env.example`의 `LLM_MODEL_DEFAULT`를 `claude-haiku-5-5`로 바꾼다. 호출 종류별 칸은 비워 두어 기본값을 따른다. `.env`를 새로 만들지 않은 곳에서도 싼 쪽으로 불리게 하려는 것이다.
- 채점(judge)은 그대로 GPT다(ADR-0006).
- 모델 성능 비교(시나리오④, PR 23)는 하지 않는다.
- 가격표(`agent/src/taxsplit/llm/pricing.toml`, `gateway/src/main/resources/pricing.yml`)의 Sonnet 줄은 지우지 않는다. 설정으로 다시 Sonnet을 쓸 수 있어야 한다.

## 검토한 대안

- 코드 기본값은 Sonnet으로 두고 `.env.example`에서 `LLM_MODEL_MAIN_AGENT`·`LLM_MODEL_VERIFIER`만 Haiku로 채우기: 코드 변경이 없지만, `.env`를 새로 만들지 않은 맥북·서버에서는 여전히 Sonnet으로 불려 비용이 약 20배 나갈 수 있다. 탈락.
- 시나리오④로 비교한 뒤 정하기: 공개 전에 비교할 시간과 비용이 없다. 탈락.

## 결과

- 좋은 점: 상담 비용이 약 1/20이 된다. 되돌리기 쉽다(설정값 `LLM_MODEL_MAIN_AGENT`·`LLM_MODEL_VERIFIER`, 또는 `LLM_MODEL_DEFAULT`만 바꾸면 된다).
- 나쁜 점: 답 품질이 Sonnet보다 떨어질 수 있다. v1 기준 수치(PR 15)를 Haiku로 재서 확인한다. 그래서 이 결정(PR 32)은 PR 15보다 먼저 merge한다.
