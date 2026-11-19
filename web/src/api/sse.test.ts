import { describe, expect, it } from "vitest";
import { sse, streamOf } from "../test/fixtures";
import { SseParser, readSse } from "./sse";

async function collect(chunks: string[]) {
  const out = [];
  for await (const e of readSse(streamOf(chunks))) out.push(e);
  return out;
}

describe("SSE 읽기", () => {
  it("이벤트 하나가 줄 중간에서 잘려 와도 이어 붙여 읽는다", async () => {
    const raw = sse("delta", { text: "안녕하세요" });
    const events = await collect([raw.slice(0, 5), raw.slice(5, 17), raw.slice(17)]);
    expect(events).toEqual([{ name: "delta", data: { text: "안녕하세요" } }]);
  });

  it("한 조각에 여러 이벤트가 와도 모두 읽는다", async () => {
    const raw = sse("status", { stage: "thinking" }) + sse("delta", { text: "a" }) + sse("delta", { text: "b" });
    const events = await collect([raw]);
    expect(events.map((e) => e.name)).toEqual(["status", "delta", "delta"]);
  });

  it("error 뒤 done까지 순서대로 읽는다", async () => {
    const raw = sse("error", { message: "AI 호출 실패" }) + sse("done", { ended: "error", turn: 1, message_id: null });
    const events = await collect([raw]);
    expect(events).toEqual([
      { name: "error", data: { message: "AI 호출 실패" } },
      { name: "done", data: { ended: "error", turn: 1, message_id: null } },
    ]);
  });

  it("한글 바이트가 조각 경계에서 잘려도 깨지지 않는다", async () => {
    const bytes = new TextEncoder().encode(sse("delta", { text: "세금" }));
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(bytes.slice(0, 30));
        c.enqueue(bytes.slice(30));
        c.close();
      },
    });
    const events = [];
    for await (const e of readSse(body)) events.push(e);
    expect(events).toEqual([{ name: "delta", data: { text: "세금" } }]);
  });

  it("CRLF 줄바꿈과 마지막 빈 줄이 없는 끝도 받아 준다", async () => {
    const events = await collect(['event: done\r\ndata: {"ended":"answered"}\r\n']);
    expect(events).toEqual([{ name: "done", data: { ended: "answered" } }]);
  });

  it("빈 줄이 오기 전까지는 이벤트를 내지 않는다", () => {
    const p = new SseParser();
    expect(p.push('event: delta\ndata: {"text":"x"}\n')).toEqual([]);
    expect(p.push("\n")).toEqual([{ name: "delta", data: { text: "x" } }]);
  });
});
