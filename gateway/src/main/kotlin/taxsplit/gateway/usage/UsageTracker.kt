package taxsplit.gateway.usage

import tools.jackson.databind.JsonNode
import tools.jackson.databind.json.JsonMapper
import java.io.ByteArrayOutputStream

/**
 * 호출 하나의 답 바이트를 옆에서 읽어 모델과 토큰 수를 모은다. 답 자체는 바꾸지 않는다.
 *
 * - 일반 답: 본문 JSON 전체의 usage.
 * - 스트리밍(SSE): 줄 단위로 끊어 `data:` 줄만 읽는다.
 *   message_start의 message.usage가 처음 값, message_delta의 usage는 누적값이라 0이 아닌 칸만 덮는다
 *   (에이전트 llm/anthropic_client.py stream과 같은 규칙).
 */
class UsageTracker(private val stream: Boolean, requestModel: String, private val mapper: JsonMapper) {
    var model: String = requestModel
        private set
    var usage = TokenUsage()
        private set

    // 일반 답은 끝까지 모으고, 스트리밍은 아직 줄바꿈이 안 온 꼬리만 들고 있는다
    private val pending = ByteArrayOutputStream()

    fun feed(bytes: ByteArray) {
        if (!stream) {
            pending.write(bytes)
            return
        }
        // 조각 경계가 줄 중간(한글 글자 중간일 수도 있음)에 올 수 있어 바이트로 줄을 찾는다
        var start = 0
        for (i in bytes.indices) {
            if (bytes[i] == NEWLINE) {
                pending.write(bytes, start, i - start)
                line(pending.toString(Charsets.UTF_8))
                pending.reset()
                start = i + 1
            }
        }
        pending.write(bytes, start, bytes.size - start)
    }

    /** 본문이 다 온 뒤 한 번 부른다. 일반 답의 usage는 여기서 읽는다. */
    fun finish() {
        val rest = pending.toString(Charsets.UTF_8)
        pending.reset()
        if (stream) {
            line(rest)
        } else {
            parse(rest)?.let { message(it) }
        }
    }

    private fun line(raw: String) {
        val text = raw.trimEnd('\r')
        if (!text.startsWith("data:")) return
        val event = parse(text.removePrefix("data:").trim()) ?: return
        when (event.path("type").asString("")) {
            "message_start" -> message(event.path("message"))
            "message_delta" -> {
                val delta = tokens(event.path("usage"))
                usage = TokenUsage(
                    inputTokens = delta.inputTokens.orElse(usage.inputTokens),
                    outputTokens = delta.outputTokens.orElse(usage.outputTokens),
                    cacheCreationInputTokens = delta.cacheCreationInputTokens.orElse(usage.cacheCreationInputTokens),
                    cacheReadInputTokens = delta.cacheReadInputTokens.orElse(usage.cacheReadInputTokens),
                )
            }
        }
    }

    private fun message(node: JsonNode) {
        node.path("model").asString("").takeIf { it.isNotEmpty() }?.let { model = it }
        if (node.has("usage")) usage = tokens(node.path("usage"))
    }

    private fun tokens(node: JsonNode) = TokenUsage(
        inputTokens = node.path("input_tokens").asLong(0),
        outputTokens = node.path("output_tokens").asLong(0),
        cacheCreationInputTokens = node.path("cache_creation_input_tokens").asLong(0),
        cacheReadInputTokens = node.path("cache_read_input_tokens").asLong(0),
    )

    // 오류 답·깨진 JSON은 토큰 0으로 둔다 (기록은 상태 코드로 남는다)
    private fun parse(text: String): JsonNode? =
        if (text.isBlank()) null else runCatching { mapper.readTree(text) }.getOrNull()

    private fun Long.orElse(previous: Long) = if (this != 0L) this else previous

    private companion object {
        const val NEWLINE = '\n'.code.toByte()
    }
}
