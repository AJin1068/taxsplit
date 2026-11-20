package taxsplit.gateway.relay

import org.springframework.core.io.buffer.DataBuffer
import org.springframework.http.HttpHeaders
import org.springframework.http.HttpStatus
import org.springframework.http.MediaType
import org.springframework.http.server.reactive.ServerHttpRequest
import org.springframework.http.server.reactive.ServerHttpResponse
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.reactive.function.client.WebClient
import reactor.core.publisher.Flux
import reactor.core.publisher.Mono
import taxsplit.gateway.GatewayProperties
import taxsplit.gateway.usage.CallLog
import taxsplit.gateway.usage.CallRecord
import taxsplit.gateway.usage.Pricing
import taxsplit.gateway.usage.UsageTracker
import tools.jackson.databind.json.JsonMapper
import java.time.Instant
import java.util.concurrent.atomic.AtomicBoolean

/**
 * POST /v1/messages 중계. 에이전트의 Anthropic SDK가 주소(LLM_BASE_URL)만 바꾸면 그대로 동작하게 한다.
 *
 * - 본문은 바꾸지 않고 그대로 넘기고, 답도 상태 코드·본문 그대로 돌려준다 (4xx·5xx 포함).
 * - 스트리밍(SSE)은 받은 조각을 모으지 않고 하나씩 바로 흘려보낸다(조각마다 flush).
 * - 답을 흘려보내면서 옆에서 토큰을 읽어 호출이 끝나면 비용 기록 한 줄을 남긴다.
 * - 레이트 리밋·재시도·서킷 브레이커·폴백은 PR 17에서 이 중계 앞뒤에 얹는다.
 */
@RestController
class MessagesController(
    webClientBuilder: WebClient.Builder,
    private val properties: GatewayProperties,
    private val pricing: Pricing,
    private val callLog: CallLog,
    private val mapper: JsonMapper,
) {
    private val upstream = webClientBuilder.baseUrl(properties.upstreamUrl).build()

    @PostMapping("/v1/messages")
    fun relay(
        @RequestBody body: ByteArray,
        request: ServerHttpRequest,
        response: ServerHttpResponse,
    ): Mono<Void> {
        val started = System.nanoTime()
        val head = runCatching { mapper.readTree(body) }.getOrNull()
        val stream = head?.path("stream")?.asBoolean(false) ?: false
        val tracker = UsageTracker(stream, head?.path("model")?.asString("") ?: "", mapper)
        val callKind = request.headers.getFirst(CALL_KIND_HEADER) ?: ""

        val recorded = AtomicBoolean(false)

        // 호출 하나에 기록 한 줄 (완료·오류·취소 중 먼저 온 것)
        fun record(status: Int, requestId: String?) {
            if (!recorded.compareAndSet(false, true)) return
            callLog.add(
                CallRecord(
                    ts = Instant.now(),
                    requestId = requestId,
                    model = tracker.model,
                    stream = stream,
                    status = status,
                    latencyMs = (System.nanoTime() - started) / 1_000_000,
                    usage = tracker.usage,
                    costUsd = if (status in 200..299) pricing.costUsd(tracker.model, tracker.usage) else null,
                    callKind = callKind,
                ),
            )
        }

        return upstream.post()
            .uri { it.path("/v1/messages").query(request.uri.rawQuery).build() }
            .headers { copyRequestHeaders(request.headers, it) }
            .bodyValue(body)
            .exchangeToMono { upstreamResponse ->
                val status = upstreamResponse.statusCode().value()
                val requestId = upstreamResponse.headers().asHttpHeaders().getFirst("request-id")
                response.statusCode = upstreamResponse.statusCode()
                copyResponseHeaders(upstreamResponse.headers().asHttpHeaders(), response.headers)
                // 조각을 읽어 기록용으로만 복사하고, 원래 조각은 그대로 내보낸다
                val chunks: Flux<DataBuffer> = upstreamResponse.bodyToFlux(DataBuffer::class.java)
                    .doOnNext { tracker.feed(bytesOf(it)) }
                    // 끝 신호가 응답으로 넘어가기 전에 기록한다 (답을 다 받은 쪽이 바로 /usage를 봐도 맞게)
                    .doOnComplete {
                        tracker.finish()
                        record(status, requestId)
                    }
                    .doOnError { record(status, requestId) }
                    .doOnCancel { record(status, requestId) }
                response.writeAndFlushWith(chunks.map { Mono.just(it) })
            }
            .onErrorResume { error ->
                // 이미 보내기 시작했으면 바꿀 수 없다. 연결 실패처럼 답을 못 받은 경우만 502
                if (response.isCommitted) return@onErrorResume Mono.error(error)
                record(HttpStatus.BAD_GATEWAY.value(), null)
                response.statusCode = HttpStatus.BAD_GATEWAY
                response.headers.contentType = MediaType.APPLICATION_JSON
                val message = mapOf(
                    "type" to "error",
                    "error" to mapOf("type" to "api_error", "message" to "gateway: upstream unreachable"),
                )
                response.writeWith(Mono.just(response.bufferFactory().wrap(mapper.writeValueAsBytes(message))))
            }
    }

    private fun copyRequestHeaders(incoming: HttpHeaders, outgoing: HttpHeaders) {
        FORWARDED_REQUEST_HEADERS.forEach { name -> incoming[name]?.let { outgoing.put(name, it) } }
        // 에이전트가 보낸 x-api-key·Authorization은 넘기지 않고 게이트웨이 키로 바꿔 끼운다
        outgoing["x-api-key"] = properties.anthropicApiKey
    }

    private fun copyResponseHeaders(incoming: HttpHeaders, outgoing: HttpHeaders) {
        incoming.forEach { name, values ->
            if (name.lowercase() !in HOP_BY_HOP_HEADERS) outgoing.put(name, values)
        }
    }

    private fun bytesOf(buffer: DataBuffer): ByteArray {
        val bytes = ByteArray(buffer.readableByteCount())
        // 읽기 위치를 움직이지 않는 복사 (원래 조각은 그대로 내보낸다)
        var offset = 0
        buffer.readableByteBuffers().use {
            it.forEach { bb ->
                val n = bb.remaining()
                bb.duplicate().get(bytes, offset, n)
                offset += n
            }
        }
        return bytes
    }

    companion object {
        const val CALL_KIND_HEADER = "X-Taxsplit-Call-Kind"

        // 넘기는 머리글만 고른다. accept-encoding을 넘기면 압축된 답이 와 토큰을 못 읽는다
        private val FORWARDED_REQUEST_HEADERS = listOf("content-type", "anthropic-version", "anthropic-beta", "accept")
        private val HOP_BY_HOP_HEADERS =
            setOf("connection", "keep-alive", "transfer-encoding", "content-length", "upgrade")
    }
}
