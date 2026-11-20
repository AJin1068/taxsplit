package taxsplit.gateway

import org.springframework.boot.autoconfigure.SpringBootApplication
import org.springframework.boot.context.properties.ConfigurationProperties
import org.springframework.boot.context.properties.ConfigurationPropertiesScan
import org.springframework.boot.runApplication
import org.springframework.context.annotation.Bean
import taxsplit.gateway.usage.Pricing

@SpringBootApplication
@ConfigurationPropertiesScan
class GatewayApplication {
    @Bean
    fun pricing(): Pricing = Pricing.bundled()
}

/**
 * 게이트웨이 설정 (application.yml의 gateway.*, 값은 환경변수에서).
 * - anthropicApiKey: 게이트웨이 자기 키. 에이전트가 보낸 x-api-key는 버리고 이 키로 바꿔 끼운다.
 * - callLog: 호출별 비용 기록(JSON 한 줄씩)을 덧붙일 파일.
 */
@ConfigurationProperties("gateway")
data class GatewayProperties(
    private val anthropicBaseUrl: String = "",
    val anthropicApiKey: String = "",
    private val callLog: String = "",
) {
    // .env에 빈 값(GATEWAY_...=)으로 들어와도 기본값을 쓴다
    val upstreamUrl: String get() = anthropicBaseUrl.ifBlank { "https://api.anthropic.com" }
    val callLogPath: String get() = callLog.ifBlank { "logs/calls.jsonl" }
}

fun main(args: Array<String>) {
    runApplication<GatewayApplication>(*args)
}
