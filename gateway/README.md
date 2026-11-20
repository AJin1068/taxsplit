# gateway

원투원의 LLM 게이트웨이입니다. 에이전트(`agent/`)의 Anthropic 호출을 받아 Anthropic Messages API로 그대로 넘기고, 호출마다 토큰과 비용을 기록합니다 (ADR-0002, PRD NFR-02·NFR-03).

- 스택: Kotlin 2.4.21, Spring Boot 4.2.0 (WebFlux, `WebClient`), JDK 21, Gradle 9.9.2 wrapper
- 지금 하는 것 (PR 16): `POST /v1/messages` 중계(스트리밍 포함), 호출별 비용 기록, `GET /usage` 합계
- 다음 (PR 17): 레이트 리밋(Redis), 재시도·타임아웃·서킷 브레이커·폴백(Resilience4j), 장애 주입

## 무엇을 하나

| 기능 | 동작 |
| --- | --- |
| 중계 | 요청 본문을 바꾸지 않고 넘긴다. 답은 상태 코드·본문 그대로 돌려준다(4xx·5xx 포함) |
| 스트리밍 | `"stream": true`면 SSE 조각을 받는 대로 하나씩 흘려보낸다(모았다가 보내지 않음) |
| API 키 | 게이트웨이 자기 `ANTHROPIC_API_KEY`를 쓴다. 에이전트가 보낸 `x-api-key`는 버린다 |
| 비용 기록 | 호출마다 JSON 한 줄을 표준 출력과 `GATEWAY_CALL_LOG` 파일에 남긴다 |
| `GET /usage` | 켠 뒤 지금까지의 호출 수·토큰·비용 합계, 호출 종류별 비용 (메모리, 다시 켜면 0) |

기록 한 줄의 칸: `ts`, `request_id`(Anthropic `request-id`), `model`, `stream`, `status`, `latency_ms`, `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `cost_usd`(단가표에 없는 모델·실패한 호출은 `null`), `call_kind`(에이전트 머리글 `X-Taxsplit-Call-Kind`, 없으면 `""`). 대화 내용·API 키는 남기지 않습니다(NFR-04).

단가표는 `src/main/resources/pricing.yml`입니다. 에이전트 단가표 `agent/src/taxsplit/llm/pricing.toml`과 값이 어긋나면 `PricingTest`가 실패합니다.

## 설정 (환경변수)

| 이름 | 기본값 | 뜻 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | (없음) | 게이트웨이가 Anthropic을 부를 때 쓰는 키 |
| `GATEWAY_ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | 넘길 곳 |
| `GATEWAY_CALL_LOG` | `logs/calls.jsonl` | 비용 기록 파일 (커밋 제외) |

## 띄우기

```bash
# 레포 루트에서. .env의 ANTHROPIC_API_KEY를 읽는다
docker compose up -d --build gateway
curl 127.0.0.1:8081/usage     # {"calls":0, ...}
```

기록 파일은 호스트의 `gateway/logs/calls.jsonl`에 쌓입니다.

## 에이전트를 게이트웨이로 돌리기

에이전트 코드는 그대로 두고 주소만 바꿉니다. 에이전트는 호출 종류(`main_agent`, `pdf_extract`, `sim_user`, `verifier`)를 `X-Taxsplit-Call-Kind` 머리글로 붙여 보냅니다. GPT 채점(`judge`)은 게이트웨이를 거치지 않습니다.

```bash
cd agent
LLM_PROVIDER=anthropic LLM_BASE_URL=http://127.0.0.1:8081 \
  uv run python -m taxsplit.harness run --only v0-02 --repeat 1
curl 127.0.0.1:8081/usage     # cost_usd 합계를 하네스 결과 파일의 상담 AI 비용과 비교
```

## 테스트

가짜 Anthropic 서버(OkHttp MockWebServer)로 돌립니다. 단가표 비교 테스트가 `../agent/`를 읽으므로 레포 루트 전체가 보여야 합니다.

```bash
cd gateway && ./gradlew test                       # JDK 21이 있을 때
# JDK 21이 없으면 (레포 루트에서)
docker run --rm -v "$PWD:/w" -w /w/gateway gradle:jdk21 ./gradlew test
```
