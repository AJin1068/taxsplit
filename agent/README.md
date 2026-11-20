# agent

맞벌이 공제 배분 에이전트의 Python(FastAPI) 서비스입니다. 계산 엔진, 에이전트 루프, 평가 실행이 여기에 있습니다.
실행 방법과 전체 구조는 레포 루트의 README.md를 보세요.

## 로컬에서 대화해 보기 (PR 10)

```bash
cp .env.example .env                 # 레포 루트에서. 연습용 Postgres 비밀번호가 들어 있다
docker compose up -d postgres
cd agent && uv sync
uv run alembic upgrade head          # "INFO  [alembic.runtime.migration] Running upgrade ..." 줄이 찍힌다
uv run uvicorn taxsplit.main:app --reload
```

- 셸에 다른 프로젝트의 `DATABASE_URL`이 있으면 `.env`보다 먼저 쓰인다. `echo $DATABASE_URL`로 확인하고, 있으면 `unset DATABASE_URL`.
- 기본은 `STORAGE=memory`, `LLM_PROVIDER=fake`(키 없이, 돈 안 듦). 실제 Claude로 보려면 `.env`에 `LLM_PROVIDER=anthropic`과 `ANTHROPIC_API_KEY`를 넣는다.

### 채팅 API

| 요청 | 하는 일 |
| --- | --- |
| `POST /conversations` `{"title", "documents"?}` | 대화 만들기. `documents`는 간소화 PDF 추출 결과(0~2개). 검사에 떨어지면 422와 칸 경로가 붙은 한국어 이유 |
| `POST /conversations/{id}/messages` `{"content"}` | 메시지 보내기. 답은 SSE(`text/event-stream`) |
| `GET /conversations/{id}/messages` | 저장된 사용자·AI 메시지(순번, 역할, 글) |

SSE 이벤트 순서: `status`(0번 이상) → `delta`(1번 이상) → `allocation`(배분 비교 성공 시) → `evidence` → `done`(늘 마지막). AI 호출이 실패하면 `error` 뒤에 `done`. 모양은 `src/taxsplit/agent/events.py`.

```bash
CID=$(curl -s localhost:8000/conversations -H 'content-type: application/json' \
  -d '{"title":"우리 집"}' | jq .id)
curl -N localhost:8000/conversations/$CID/messages -H 'content-type: application/json' \
  -d '{"content":"남편 총급여 6,200만 원(1984년생), 아내 3,800만 원(1986년생). 아이 하늘 2016년생, 남편 어머니 봄 1954년생, 둘 다 소득 없음. 봄 의료비 420만 원은 아내가 냈어요. 누구에게 넣을까요?"}'
```

AI가 쓴 답은 다 받은 뒤 센서 3개(금액·판정·계산 전 답 금지)로 검사하고, 통과한 답만 조각으로 나눠 보낸다. 그래서 첫 글자가 조금 늦게 나온다.
