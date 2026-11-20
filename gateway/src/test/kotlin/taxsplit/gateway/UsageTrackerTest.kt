package taxsplit.gateway

import taxsplit.gateway.usage.TokenUsage
import taxsplit.gateway.usage.UsageTracker
import tools.jackson.databind.json.JsonMapper
import kotlin.test.Test
import kotlin.test.assertEquals

class UsageTrackerTest {
    private val mapper = JsonMapper.builder().build()

    @Test
    fun `일반 답은 본문 usage와 모델을 읽는다`() {
        val tracker = UsageTracker(stream = false, requestModel = "claude-sonnet-5-5", mapper = mapper)
        val body = Fixtures.MESSAGE_JSON.toByteArray()
        tracker.feed(body.copyOfRange(0, 10))
        tracker.feed(body.copyOfRange(10, body.size))
        tracker.finish()
        assertEquals(TokenUsage(12, 4, 3, 5), tracker.usage)
        assertEquals("claude-sonnet-5-5", tracker.model)
    }

    @Test
    fun `스트리밍은 message_start와 message_delta usage를 모은다 - 조각이 줄·글자 중간에서 끊겨도`() {
        val tracker = UsageTracker(stream = true, requestModel = "", mapper = mapper)
        val body = Fixtures.SSE.toByteArray()
        // 7바이트씩 잘라 넣는다 (한글 3바이트 글자도 중간에서 잘린다)
        body.toList().chunked(7).forEach { tracker.feed(it.toByteArray()) }
        tracker.finish()
        assertEquals(TokenUsage(inputTokens = 12, outputTokens = 4, cacheCreationInputTokens = 0, cacheReadInputTokens = 2), tracker.usage)
        assertEquals("claude-haiku-5-5", tracker.model)
    }

    @Test
    fun `오류 답은 토큰 0`() {
        val tracker = UsageTracker(stream = false, requestModel = "claude-sonnet-5-5", mapper = mapper)
        tracker.feed(Fixtures.ERROR_JSON.toByteArray())
        tracker.finish()
        assertEquals(TokenUsage(), tracker.usage)
    }
}
