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

## 평가 하네스 (PR 11)

시나리오(`eval/scenarios/v0/`)마다 "가상 사용자(AI) ↔ 메인 에이전트" 대화를 채팅 API로 돌리고, `eval/scoring/score.py`로 채점해 결과 JSON을 `eval-runs/`에 쓴다. 명령 하나로 실행·채점·저장·비교까지 한다.

```bash
cd agent
# 실제 API (돈이 든다. 10개 × 3번에 약 10달러, 상한 기본 10달러)
LLM_PROVIDER=anthropic uv run python -m taxsplit.harness run
# 한 시나리오만 한 번
LLM_PROVIDER=anthropic uv run python -m taxsplit.harness run --only v0-02 --repeat 1
# 기준 결과와 비교(떨어지면 끝 값 1)
LLM_PROVIDER=anthropic uv run python -m taxsplit.harness run --baseline eval-runs/<기준>.json
# v0과 v1을 한 번에 돌려 결과 파일·요약 하나로(PR 11c)
LLM_PROVIDER=anthropic uv run python -m taxsplit.harness run \
  --scenarios ../eval/scenarios/v0 --scenarios ../eval/scenarios/v1
```

| 옵션 | 뜻 |
| --- | --- |
| `--scenarios <폴더>` | 시나리오 폴더(기본 `eval/scenarios/v0`). 레포 밖 홀드아웃 폴더도 읽는다. 여러 번 주면 한 결과로 묶고, 시나리오 id가 겹치면 시작 전에 멈춘다 |
| `--repeat N` | 시나리오마다 반복 수(기본 3) |
| `--only <id>` | 그 시나리오만(여러 번 줄 수 있음) |
| `--judge` | GPT 채점(최종 설명이 배분 결과와 맞나)도 한다. `OPENAI_API_KEY` 필요 |
| `--baseline <JSON>` | 기준 결과와 비교: 떨어짐 / 같음 또는 좋아짐 / 비용 늘어남(경고) |
| `--out <경로>` | 결과 JSON 경로(기본 `eval-runs/<날짜>-run.json`, 덮어쓰지 않음) |
| `--max-cost-usd N` | 누적 비용 상한(기본 10). 넘으면 새 대화를 시작하지 않고 저장 |
| `--base-url <주소>` | 떠 있는 서버를 부른다. 없으면 같은 프로세스에 앱을 띄운다 |

- 가상 사용자 모델은 `LLM_MODEL_SIM_USER`(예: `claude-haiku-5-5`), 채점 모델은 `LLM_MODEL_JUDGE`(비면 `gpt-6.2-sol`).
- 끝 값: 0 정상, 1 기준보다 떨어짐, 2 설정·시나리오 오류(파일 이름과 칸을 알려 줌).
- 실행 기록에는 대화 중 화면에 낸 빈 곳 알림 카드가 `gaps`(카드 `id`, 주인 `member`: 관계·출생연도, 가구 전체 질문이면 `null`)로 남는다. 정답(`gaps_expected`)이 있는 시나리오(v1~)면 요약에 빈 곳 알림 적중률·오알림 수가 나온다.
- pytest는 가짜 LLM으로 같은 명령을 끝까지 돌린다(`tests/harness/`, 돈이 들지 않음).
