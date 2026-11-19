// 에이전트 채팅 API 부르기. 개발 서버가 /api를 에이전트 API로 넘긴다(vite.config.ts).
import { readSse } from "./sse";
import type { ChatEvent } from "./types";

const BASE = "/api";

/** 대화 만들기. 간소화 자료(추출 결과 JSON)가 있으면 함께 보낸다. */
export async function createConversation(title: string, documents: unknown[] = []): Promise<number> {
  const res = await fetch(`${BASE}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, documents }),
  });
  if (!res.ok) throw new Error(`대화를 만들지 못했어요 (${res.status})`);
  const body = (await res.json()) as { id: number };
  return body.id;
}

/** 메시지를 보내고 SSE 이벤트를 받는 대로 내놓는다. */
export async function* sendMessage(conversationId: number, content: string): AsyncGenerator<ChatEvent> {
  const res = await fetch(`${BASE}/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok || !res.body) throw new Error(`메시지를 보내지 못했어요 (${res.status})`);
  for await (const event of readSse(res.body)) {
    yield event as ChatEvent;
  }
}
