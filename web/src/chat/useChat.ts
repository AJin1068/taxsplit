// 채팅 흐름: 첫 메시지 때 대화를 만들고(간소화 자료·첫 화면 설정 함께), 메시지를 보내 SSE를 받아 상태에 넣는다.
import { useCallback, useReducer, useRef } from "react";
import { createConversation, sendMessage } from "../api/client";
import type { CardAnswer, SetupChoice } from "../api/types";
import { chatReducer, initialState } from "./reducer";

const TITLE_CHARS = 40;

const NO_SETUP: SetupChoice = { self_role: null, child_count: null };

export function useChat(documents: unknown[], setup: SetupChoice = NO_SETUP) {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const conversationId = useRef<number | null>(null);
  const lastUserText = useRef("");
  const lastAnswer = useRef<CardAnswer | undefined>(undefined);

  // answer: 질문 카드 선택지를 눌렀으면 그 답(글과 함께 보낸다)
  const send = useCallback(
    async (text: string, answer?: CardAnswer) => {
      const content = text.trim();
      if (!content) return;
      lastUserText.current = content;
      lastAnswer.current = answer;
      dispatch({ type: "send", text: content });
      try {
        if (conversationId.current === null) {
          conversationId.current = await createConversation(content.slice(0, TITLE_CHARS), documents, setup);
        }
        let gotDone = false;
        for await (const event of sendMessage(conversationId.current, content, answer)) {
          dispatch({ type: "event", event });
          if (event.name === "done") gotDone = true;
        }
        // done 없이 연결이 끊기면 실패로 본다
        if (!gotDone) dispatch({ type: "failed" });
      } catch {
        dispatch({ type: "failed" });
      }
    },
    [documents, setup],
  );

  // 다시 보내기: 마지막으로 보낸 글(과 카드 답)을 그대로 다시 보낸다
  const retry = useCallback(() => send(lastUserText.current, lastAnswer.current), [send]);

  // 첫 메시지를 보낸 뒤에는 간소화 자료를 바꿀 수 없다
  return { state, send, retry, started: state.messages.length > 0 };
}
