package taxsplit.gateway

import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import org.springframework.beans.factory.annotation.Value
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.core.io.buffer.DataBuffer
import org.springframework.core.io.buffer.DataBufferUtils
import org.springframework.test.context.DynamicPropertyRegistry
import org.springframework.test.context.DynamicPropertySource
import org.springframework.web.reactive.function.client.WebClient
import tools.jackson.databind.JsonNode
import tools.jackson.databind.json.JsonMapper
import java.nio.file.Files
import java.nio.file.Path
import java.util.concurrent.TimeUnit
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** 가짜 Anthropic 서버(MockWebServer)를 두고 게이트웨이를 실제 포트로 띄워 중계를 본다. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class MessagesRelayTest {
    @Value("\${local.server.port}")
    var port: Int = 0

    private val mapper = JsonMapper.builder().build()
    private val client by lazy { WebClient.create("http://localhost:$port") }

    private fun post(body: String, callKind: String? = "main_agent"): Pair<Int, String> =
        client.post().uri("/v1/messages")
            .header("content-type", "application/json")
            .header("anthropic-version", "2023-06-01")
            .header("x-api-key", "sk-agent-should-be-dropped")
            .headers { h -> callKind?.let { h.set("X-Taxsplit-Call-Kind", it) } }
            .bodyValue(body)
            .exchangeToMono { r -> r.bodyToMono(String::class.java).defaultIfEmpty("").map { r.statusCode().value() to it } }
            .block()!!

    private fun lastRecord(): JsonNode = mapper.readTree(Files.readAllLines(CALL_LOG).last())

    private fun usage(): JsonNode = mapper.readTree(client.get().uri("/usage").retrieve().bodyToMono(String::class.java).block())

    @Test
    fun `일반 호출은 본문 그대로 넘기고 답을 그대로 돌려주며 키를 바꿔 끼운다`() {
        anthropic.enqueue(
            MockResponse.Builder().code(200).addHeader("content-type", "application/json")
                .addHeader("request-id", "req_ok").body(Fixtures.MESSAGE_JSON).build(),
        )
        val body = """{"model":"claude-sonnet-5-5","max_tokens":100,"messages":[{"role":"user","content":"안녕"}]}"""
        val before = usage()

        val (status, answer) = post(body)

        val sent = anthropic.takeRequest()
        assertEquals(200, status)
        assertEquals(Fixtures.MESSAGE_JSON, answer)
        assertEquals("/v1/messages", sent.url.encodedPath)
        assertEquals(body, sent.body!!.utf8())
        assertEquals("sk-gateway-test", sent.headers["x-api-key"])
        assertEquals("2023-06-01", sent.headers["anthropic-version"])
        assertNull(sent.headers["X-Taxsplit-Call-Kind"])

        // 기록 한 줄의 칸과 비용: (2*12 + 2.5*3 + 0.1*5 + 10*4) / 1e6 = 72 / 1e6
        val record = lastRecord()
        val fields = listOf(
            "ts", "request_id", "model", "stream", "status", "latency_ms", "input_tokens", "output_tokens",
            "cache_creation_input_tokens", "cache_read_input_tokens", "cost_usd", "call_kind",
        )
        assertEquals(fields, record.propertyNames().toList())
        assertEquals("req_ok", record["request_id"].asString())
        assertEquals(false, record["stream"].asBoolean())
        assertEquals(200, record["status"].asInt())
        assertEquals(listOf(12L, 4L, 3L, 5L), fields.subList(6, 10).map { record[it].asLong() })
        assertEquals("0.000072", record["cost_usd"].decimalValue().toPlainString())
        assertEquals("main_agent", record["call_kind"].asString())
        assertTrue(!Files.readString(CALL_LOG).contains("sk-"), "기록에 키가 남으면 안 된다")

        // GET /usage 합계가 이 호출만큼 늘어난다
        val after = usage()
        assertEquals(before["calls"].asInt() + 1, after["calls"].asInt())
        assertEquals(before["input_tokens"].asLong() + 12, after["input_tokens"].asLong())
        assertEquals(
            before["cost_usd"].decimalValue() + "0.000072".toBigDecimal(),
            after["cost_usd"].decimalValue(),
        )
        assertTrue(after["cost_usd_by_call_kind"]["main_agent"].decimalValue() >= "0.000072".toBigDecimal())
    }

    @Test
    fun `스트리밍은 조각을 모으지 않고 받는 대로 흘려보낸다`() {
        val first = Fixtures.SSE_EVENTS.first().toByteArray().size.toLong()
        anthropic.enqueue(
            MockResponse.Builder().code(200).addHeader("content-type", "text/event-stream")
                // 첫 이벤트를 보낸 뒤 조각마다 0.4초씩 쉰다
                .body(Fixtures.SSE).throttleBody(first, 400, TimeUnit.MILLISECONDS).build(),
        )
        val body = """{"model":"claude-haiku-5-5","max_tokens":10,"stream":true,"messages":[]}"""
        val arrivals = mutableListOf<Pair<Long, String>>()

        client.post().uri("/v1/messages").header("content-type", "application/json")
            .header("X-Taxsplit-Call-Kind", "sim_user").bodyValue(body)
            .retrieve().bodyToFlux(DataBuffer::class.java)
            .doOnNext { buf ->
                arrivals += System.nanoTime() to buf.toString(Charsets.UTF_8)
                DataBufferUtils.release(buf)
            }
            .blockLast()

        assertEquals(Fixtures.SSE, arrivals.joinToString("") { it.second })
        assertTrue(arrivals.first().second.contains("message_start"))
        val gapMs = (arrivals.last().first - arrivals.first().first) / 1_000_000
        assertTrue(gapMs >= 300, "첫 조각이 마지막 조각보다 먼저 와야 한다 (간격 ${gapMs}ms)")

        anthropic.takeRequest()
        val record = lastRecord()
        assertEquals(true, record["stream"].asBoolean())
        assertEquals("claude-haiku-5-5", record["model"].asString())
        assertEquals(listOf(12L, 4L, 2L), listOf("input_tokens", "output_tokens", "cache_read_input_tokens").map { record[it].asLong() })
        assertEquals("sim_user", record["call_kind"].asString())
    }

    @Test
    fun `4xx·5xx는 상태와 본문을 그대로 돌려주고 그 상태로 기록한다`() {
        for (code in listOf(400, 429, 500, 529)) {
            anthropic.enqueue(
                MockResponse.Builder().code(code).addHeader("content-type", "application/json")
                    .body(Fixtures.ERROR_JSON).build(),
            )
            val (status, answer) = post("""{"model":"claude-sonnet-5-5","messages":[]}""", callKind = null)
            anthropic.takeRequest()
            assertEquals(code, status)
            assertEquals(Fixtures.ERROR_JSON, answer)
            val record = lastRecord()
            assertEquals(code, record["status"].asInt())
            assertTrue(record["cost_usd"].isNull)
            assertEquals("", record["call_kind"].asString())
        }
    }

    @Test
    fun `단가표에 없는 모델은 비용이 빈 값`() {
        anthropic.enqueue(
            MockResponse.Builder().code(200).addHeader("content-type", "application/json")
                .body(Fixtures.MESSAGE_JSON.replace("claude-sonnet-5-5", "claude-unknown-9")).build(),
        )
        post("""{"model":"claude-unknown-9","messages":[]}""")
        anthropic.takeRequest()
        assertTrue(lastRecord()["cost_usd"].isNull)
        assertTrue(usage()["unpriced_calls"].asInt() >= 1)
    }

    companion object {
        val anthropic = MockWebServer().apply { start() }
        val CALL_LOG: Path = Files.createTempDirectory("gateway-test").resolve("logs/calls.jsonl")

        @JvmStatic
        @DynamicPropertySource
        fun properties(registry: DynamicPropertyRegistry) {
            registry.add("gateway.anthropic-base-url") { anthropic.url("/").toString().trimEnd('/') }
            registry.add("gateway.anthropic-api-key") { "sk-gateway-test" }
            registry.add("gateway.call-log") { CALL_LOG.toString() }
        }
    }
}
