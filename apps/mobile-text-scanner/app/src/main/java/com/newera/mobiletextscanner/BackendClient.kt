package com.newera.mobiletextscanner

import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

object BackendClient {
    fun postContractAnalysis(
        baseUrl: String,
        payload: ContractAnalysisPayload,
        devUserId: String,
    ): String {
        val normalizedBaseUrl = baseUrl.trim().trimEnd('/')
        require(normalizedBaseUrl.isNotBlank()) { "Backend URL is required" }

        val connection = URL("$normalizedBaseUrl/api/jobs/documents/contract-analysis")
            .openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.connectTimeout = 10_000
        connection.readTimeout = 30_000
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        connection.setRequestProperty("Accept", "application/json")
        if (devUserId.isNotBlank()) {
            connection.setRequestProperty("X-New-Era-User-Id", devUserId.trim())
        }

        val body = payload.toJson().toString().toByteArray(Charsets.UTF_8)
        connection.outputStream.use { stream ->
            stream.write(body)
        }

        val responseCode = connection.responseCode
        val stream = if (responseCode < 400) connection.inputStream else connection.errorStream
        val responseBody = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
        connection.disconnect()

        if (responseCode >= 400) {
            throw IOException("HTTP $responseCode $responseBody")
        }
        return responseBody
    }
}
