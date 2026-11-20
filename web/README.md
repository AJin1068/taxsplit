# web

원투원 화면(React). 첫 화면 설정(UI-00), PDF 올리기·추출 확인 표(UI-03), 스트리밍 채팅(UI-04),
빈 곳 알림 카드(FR-11), 배분안 비교 카드(UI-01)와 근거 조문 칩(UI-02)이 있습니다.
화면은 에이전트 채팅 API만 부르고 금액을 계산하지 않습니다(금액은 모두 API 값 그대로, 표시 형식만 바꿈).

## 실행

```bash
# 1) 에이전트 API 켜기 (레포 루트 README·agent/README.md 참고)
cd agent && uv run uvicorn taxsplit.main:app --reload    # http://localhost:8000

# 2) 화면 켜기 (Node 버전은 .nvmrc)
cd web && npm install && npm run dev                     # http://localhost:5173
```

- 개발 서버가 `/api`로 시작하는 요청을 에이전트 API로 넘깁니다(Vite 프록시). 그래서 에이전트 쪽 CORS 설정이 필요 없습니다.
- 에이전트 API를 다른 주소로 띄웠으면 `AGENT_API_URL=http://localhost:8080 npm run dev`.
- 실제 Claude로 보려면 에이전트 쪽 `.env`에 `LLM_PROVIDER=anthropic`과 키를 넣습니다. 기본(`fake`)은 정해진 짧은 답만 와서 배분안 카드가 나오지 않습니다.
- 화면 위 설정 카드에서 "저는 남편/아내"와 자녀 수(0~5명)를 고르면 첫 메시지 때 대화 만들기(`POST /conversations`의 `self_role`·`child_count`)로 보냅니다. 고르지 않아도 됩니다.
- "PDF 올리기"는 파일마다 `POST /extractions`(본문 JSON: `{"filename", "pdf_base64"}` 또는 `{"filename", "json": <추출 형식>}`)를 부르고, 읽은 값을 표로 보여 줍니다. 표에서 고친 금액·가족이 `documents`로 갑니다(고치면 PDF 합계 대조 칸 `totals`는 뺍니다).
- "견본으로 해 보기"에서 예시를 고르면 PDF 없이 가상 자료로 시작합니다(올린 자료가 있으면 견본은 쓰지 않음).

### 맥북에서 실제 Claude로 확인하기

```bash
# agent/.env에 LLM_PROVIDER=anthropic과 ANTHROPIC_API_KEY (PDF 추출은 Haiku, 돈이 듭니다)
cd agent && uv run uvicorn taxsplit.main:app --reload
cd web && npm run dev
# 브라우저 http://localhost:5173 → "저는 아내"·자녀 수 고르기 → PDF 올리기(agent/tests/unit/extract/fixtures/doc1_2025.pdf)
# → 표 확인 → 가족·연봉을 채팅으로 → 배분안 카드의 근거 칩에 마우스 올리기 → 스크린샷
```

## 테스트·빌드

```bash
npm test         # Vitest: SSE 읽기, 금액 표시, 카드, 채팅 화면
npm run build    # 타입 검사 + 빌드
```

## 폴더

| 위치 | 하는 일 |
| --- | --- |
| `src/api/` | API 모양(`types.ts`), SSE 읽기(`sse.ts`), 대화·메시지 부르기(`client.ts`) |
| `src/chat/` | 화면 상태(`reducer.ts`, useReducer)와 보내기 흐름(`useChat.ts`) |
| `src/components/` | 말풍선, 입력 칸, 첫 화면 설정(`Setup`), 추출 확인 표(`ExtractReview`), 배분안 카드와 근거 칩(`EvidenceChip`), 빈 곳 카드(`GapCard`), 견본 고르기 |
| `src/chat/events.ts` | evidence·gaps 이벤트 읽기(모르는 칸 무시), 근거를 가족 줄에 붙이는 규칙 |
| `src/format/money.ts` | 금액 표시(만 원 버림 큰 글씨 + 원 단위 작은 글씨) |
| `src/labels.ts` | 화면에 보이는 쉬운 말(도구 이름 → 진행 한 줄, 고지 문구) |
| `screenshots/` | 화면 확인 스크린샷(1~2: PR 14a, 3~5: PR 14b 가짜 API로 찍음) |
