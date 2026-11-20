package taxsplit.gateway.usage

import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RestController

@RestController
class UsageController(private val callLog: CallLog) {
    /** 게이트웨이를 켠 뒤 지금까지의 호출 수·토큰·비용 합계 (호출 종류별 비용 포함). */
    @GetMapping("/usage")
    fun usage(): Map<String, Any> = callLog.summary()
}
