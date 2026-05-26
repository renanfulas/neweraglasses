package com.newera.mobiletextscanner

import org.json.JSONObject

data class ContractAnalysisPayload(
    val sessionId: String,
    val artifactLabel: String,
    val idempotencyKey: String,
    val documentText: String,
    val observationId: String,
    val correlationId: String,
    val traceId: String,
) {
    fun toJson(): JSONObject {
        return JSONObject()
            .put("session_id", sessionId)
            .put("artifact_label", artifactLabel)
            .put("source_type", "mobile_text_scanner")
            .put("idempotency_key", idempotencyKey)
            .put("document_text", documentText)
            .put("mode", "balanced")
            .put("recent_category_count", 0)
            .put("observation_id", observationId)
            .put("correlation_id", correlationId)
            .put("trace_id", traceId)
    }
}
