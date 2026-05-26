package com.newera.mobiletextscanner

import android.graphics.Bitmap
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import java.io.Closeable

class MlKitTextScanner : Closeable {
    private val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)

    fun scan(
        bitmap: Bitmap,
        onSuccess: (String) -> Unit,
        onFailure: (Exception) -> Unit,
    ) {
        val image = InputImage.fromBitmap(bitmap, 0)
        recognizer.process(image)
            .addOnSuccessListener { result ->
                onSuccess(ScannerTextNormalizer.normalize(result.text))
            }
            .addOnFailureListener { error ->
                onFailure(error)
            }
    }

    override fun close() {
        recognizer.close()
    }
}
