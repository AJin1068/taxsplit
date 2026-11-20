// 에이전트 API 부르기. 개발 서버가 /api를 에이전트 API로 넘긴다(vite.config.ts).
import { readSse } from "./sse";
import type { CardAnswer, ChatEvent, ExtractionResponse, SetupChoice } from "./types";

const BASE = "/api";
const NO_SETUP: SetupChoice = { self_role: null, child_count: null };

/** 대화 만들기. 간소화 자료(추출 결과 JSON)와 첫 화면 설정(고른 것만)을 함께 보낸다. */
export async function createConversation(
  title: string,
  documents: unknown[] = [],
  setup: SetupChoice = NO_SETUP,
): Promise<number> {
  const body: Record<string, unknown> = { title, documents };
  // 고르지 않은 칸은 보내지 않는다(서버가 "없음"으로 저장)
  if (setup.self_role !== null) body.self_role = setup.self_role;
  if (setup.child_count !== null) body.child_count = setup.child_count;
  const res = await fetch(`${BASE}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`대화를 만들지 못했어요 (${res.status})`);
  const created = (await res.json()) as { id: number };
  return created.id;
}

/** 메시지를 보내고 SSE 이벤트를 받는 대로 내놓는다. 질문 카드 답이 있으면 answer로 함께 보낸다. */
export async function* sendMessage(
  conversationId: number,
  content: string,
  answer?: CardAnswer,
): AsyncGenerator<ChatEvent> {
  const res = await fetch(`${BASE}/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(answer ? { content, answer } : { content }),
  });
  if (!res.ok || !res.body) throw new Error(`메시지를 보내지 못했어요 (${res.status})`);
  for await (const event of readSse(res.body)) {
    yield event as ChatEvent;
  }
}

/** 파일 → base64 글자(브라우저 btoa는 글자 하나씩 넣어야 해서 조금씩 끊어 바꾼다). */
async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

/** 간소화 PDF 또는 추출 형식 JSON 파일 하나를 읽게 한다(POST /extractions). */
export async function extractFile(file: File): Promise<ExtractionResponse> {
  const isJson = file.name.toLowerCase().endsWith(".json") || file.type === "application/json";
  let payload: Record<string, unknown>;
  if (isJson) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      throw new Error("JSON 파일을 읽지 못했어요");
    }
    payload = { filename: file.name, json: parsed };
  } else {
    payload = { filename: file.name, pdf_base64: await toBase64(file) };
  }
  const res = await fetch(`${BASE}/extractions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res.status === 422) {
    // 잘못된 파일: 서버가 한국어 이유 목록을 준다
    const body = (await res.json()) as { detail?: unknown };
    const lines = Array.isArray(body.detail) ? body.detail.filter((d) => typeof d === "string") : [];
    throw new Error(lines.join(" / ") || "파일을 읽지 못했어요");
  }
  if (!res.ok) throw new Error(`파일을 읽지 못했어요 (${res.status})`);
  return (await res.json()) as ExtractionResponse;
}
