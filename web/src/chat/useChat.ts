// 채팅 흐름: 첫 메시지 때 대화를 만들고(간소화 자료 함께), 메시지를 보내 SSE를 받아 상태에 넣는다.
import { useCallback, useReducer, useRef } from "react";
import { createConversation, sendMessage } from "../api/client";
import { chatReducer, initialState } from "./reducer";

const TITLE_CHARS = 40;

export function useChat(documents: unknown[]) {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const conversationId = useRef<number | null>(null);
  const lastUserText = useRef("");

  const send = useCallback(
    async (text: string) => {
      const content = text.trim();
      if (!content) return;
      lastUserText.current = content;
      dispatch({ type: "send", text: content });
      try {
        if (conversationId.current === null) {
          conversationId.current = await createConversation(content.slice(0, TITLE_CHARS), documents);
        }
        let gotDone = false;
        for await (const event of sendMessage(conversationId.current, content)) {
          dispatch({ type: "event", event });
          if (event.name === "done") gotDone = true;
        }
        // done 없이 연결이 끊기면 실패로 본다
        if (!gotDone) dispatch({ type: "failed" });
      } catch {
        dispatch({ type: "failed" });
      }
    },
    [documents],
  );

  // 다시 보내기: 마지막으로 보낸 글을 그대로 다시 보낸다
  const retry = useCallback(() => send(lastUserText.current), [send]);

  // 첫 메시지를 보낸 뒤에는 간소화 자료를 바꿀 수 없다
  return { state, send, retry, started: state.messages.length > 0 };
}
