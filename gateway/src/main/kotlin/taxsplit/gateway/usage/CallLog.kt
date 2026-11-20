package taxsplit.gateway.usage

import org.slf4j.LoggerFactory
import org.springframework.stereotype.Component
import taxsplit.gateway.GatewayProperties
import tools.jackson.databind.json.JsonMapper
import java.math.BigDecimal
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardOpenOption
import java.time.Instant

/** 호출 하나의 비용 기록. 대화 내용·가족 정보·API 키는 넣지 않는다 (NFR-04). */
data class CallRecord(
    val ts: Instant,
    val requestId: String?,
    val model: String,
    val stream: Boolean,
    val status: Int,
    val latencyMs: Long,
    val usage: TokenUsage,
    val costUsd: BigDecimal?, // 단가표에 없는 모델은 null (0 아님)
    val callKind: String, // 에이전트 머리글 X-Taxsplit-Call-Kind, 없으면 ""
) {
    fun toMap(): Map<String, Any?> = linkedMapOf(
        "ts" to ts.toString(),
        "request_id" to requestId,
        "model" to model,
        "stream" to stream,
        "status" to status,
        "latency_ms" to latencyMs,
        "input_tokens" to usage.inputTokens,
        "output_tokens" to usage.outputTokens,
        "cache_creation_input_tokens" to usage.cacheCreationInputTokens,
        "cache_read_input_tokens" to usage.cacheReadInputTokens,
        "cost_usd" to costUsd,
        "call_kind" to callKind,
    )
}

/**
 * 호출별 비용 기록 (NFR-02). DB 없이:
 * - 표준 출력에 JSON 한 줄 + 파일(GATEWAY_CALL_LOG)에 JSON 한 줄 덧붙이기
 * - GET /usage 합계는 메모리에서 센다 (다시 켜면 0)
 */
@Component
class CallLog(properties: GatewayProperties, private val mapper: JsonMapper) {
    private val log = LoggerFactory.getLogger("taxsplit.gateway.calls")
    private val file: Path = Path.of(properties.callLogPath)
    private val records = mutableListOf<CallRecord>()

    @Synchronized
    fun add(record: CallRecord) {
        val line = mapper.writeValueAsString(record.toMap())
        records += record
        log.info(line)
        // 파일 쓰기가 실패해도 중계는 계속한다 (기록은 표준 출력에 남아 있다)
        runCatching {
            file.toAbsolutePath().parent?.let { Files.createDirectories(it) }
            Files.writeString(file, line + "\n", StandardOpenOption.CREATE, StandardOpenOption.APPEND)
        }.onFailure { log.warn("호출 기록 파일 쓰기 실패: {}", it.toString()) }
    }

    /** 지금까지 기록의 합계. 비용은 단가가 있는 호출만 더하고, 없는 호출 수는 따로 센다. */
    @Synchronized
    fun summary(): Map<String, Any> {
        val byKind = sortedMapOf<String, BigDecimal>()
        records.forEach { r -> r.costUsd?.let { byKind.merge(r.callKind, it, BigDecimal::add) } }
        return linkedMapOf(
            "calls" to records.size,
            "input_tokens" to records.sumOf { it.usage.inputTokens },
            "output_tokens" to records.sumOf { it.usage.outputTokens },
            "cache_creation_input_tokens" to records.sumOf { it.usage.cacheCreationInputTokens },
            "cache_read_input_tokens" to records.sumOf { it.usage.cacheReadInputTokens },
            "cost_usd" to records.mapNotNull { it.costUsd }.fold(BigDecimal.ZERO, BigDecimal::add),
            "unpriced_calls" to records.count { it.costUsd == null },
            "cost_usd_by_call_kind" to byKind,
        )
    }
}
