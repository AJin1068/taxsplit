// SSE(text/event-stream) 읽기.
// 브라우저 EventSource는 POST를 못 보내서, fetch 응답 스트림을 직접 읽는다.
// 네트워크 조각은 줄 중간에서 잘려 올 수도, 여러 이벤트가 한 번에 올 수도 있다.

export interface RawEvent {
  name: string;
  data: unknown;
}

export class SseParser {
  private buffer = "";

  /** 받은 글 조각을 넣으면, 빈 줄로 끝난(완성된) 이벤트만 돌려준다. 남은 글은 다음 조각을 기다린다. */
  push(chunk: string): RawEvent[] {
    this.buffer += chunk.replace(/\r\n?/g, "\n");
    const events: RawEvent[] = [];
    let end = this.buffer.indexOf("\n\n");
    while (end !== -1) {
      const block = this.buffer.slice(0, end);
      this.buffer = this.buffer.slice(end + 2);
      const event = parseBlock(block);
      if (event) events.push(event);
      end = this.buffer.indexOf("\n\n");
    }
    return events;
  }
}

/** 이벤트 한 덩어리(`event:` 줄 + `data:` 줄들)를 읽는다. 이름이나 값이 없으면 버린다. */
function parseBlock(block: string): RawEvent | null {
  let name = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
  }
  if (dataLines.length === 0) return null;
  try {
    return { name, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

/** 응답 본문 스트림을 이벤트 단위로 하나씩 내놓는다. */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<RawEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      yield* parser.push(decoder.decode(value, { stream: true }));
    }
    // 마지막 빈 줄이 빠진 채 끝나도 남은 이벤트를 살린다
    yield* parser.push(decoder.decode() + "\n\n");
  } finally {
    reader.releaseLock();
  }
}
