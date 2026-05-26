package com.newera.mobiletextscanner

import java.security.MessageDigest

object ScannerTextNormalizer {
    const val MIN_DOCUMENT_TEXT_LENGTH = 20
    const val MAX_DOCUMENT_TEXT_LENGTH = 50_000

    fun normalize(rawText: String): String {
        val normalizedLineEndings = rawText
            .replace("\r\n", "\n")
            .replace("\r", "\n")
        val withoutControls = normalizedLineEndings.filter { char ->
            char == '\n' || char == '\t' || !char.isISOControl()
        }
        val trimmedLines = withoutControls
            .lines()
            .joinToString("\n") { it.trimEnd() }
        return trimmedLines
            .replace(Regex("\n{3,}"), "\n\n")
            .trim()
    }

    fun validationError(text: String): String? {
        return when {
            text.length < MIN_DOCUMENT_TEXT_LENGTH ->
                "Text is too short for contract analysis"

            text.length > MAX_DOCUMENT_TEXT_LENGTH ->
                "Text is too long; review or split before submit"

            else -> null
        }
    }

    fun stableIdempotencyKey(text: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
            .digest(text.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
            .take(24)
        return "scan_$digest"
    }
}
