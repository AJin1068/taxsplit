# web

원투원 화면(React). 스트리밍 채팅(UI-04)과 배분안 비교 카드(UI-01)가 있습니다.
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
- 화면 위 "개발용 간소화 자료"에서 예시를 고르면 첫 메시지 때 대화와 함께 보냅니다(가상 인물).

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
| `src/components/` | 말풍선, 입력 칸, 배분안 카드, 개발용 자료 고르기 |
| `src/format/money.ts` | 금액 표시(만 원 버림 큰 글씨 + 원 단위 작은 글씨) |
| `src/labels.ts` | 화면에 보이는 쉬운 말(도구 이름 → 진행 한 줄, 고지 문구) |
| `screenshots/` | PR 14a 화면 확인 스크린샷 |
