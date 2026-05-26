package com.newera.mobiletextscanner

import android.graphics.Bitmap
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.MediaStore
import android.text.InputType
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.setPadding
import java.util.UUID

class MainActivity : ComponentActivity() {
    private val scanner = MlKitTextScanner()

    private lateinit var backendUrlInput: EditText
    private lateinit var devUserInput: EditText
    private lateinit var sessionInput: EditText
    private lateinit var textInput: EditText
    private lateinit var statusView: TextView
    private lateinit var responseView: TextView

    private val takePhoto = registerForActivityResult(ActivityResultContracts.TakePicturePreview()) { bitmap ->
        if (bitmap == null) {
            setStatus("Capture cancelled")
        } else {
            scanBitmap(bitmap)
        }
    }

    private val pickImage = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri == null) {
            setStatus("Image selection cancelled")
        } else {
            scanUri(uri)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildUi()
    }

    override fun onDestroy() {
        scanner.close()
        super.onDestroy()
    }

    private fun buildUi() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32)
        }

        root.addView(TextView(this).apply {
            text = "New Era Scanner"
            textSize = 24f
            gravity = Gravity.CENTER_HORIZONTAL
        })

        backendUrlInput = editText("Backend URL", "http://10.0.2.2:8000")
        devUserInput = editText("Local dev user header", "local-demo-user")
        sessionInput = editText("Session ID", "session_mobile_text_scanner")
        textInput = editText("Extracted contract text", "", multiline = true)
        statusView = TextView(this)
        responseView = TextView(this).apply {
            textIsSelectable = true
        }

        root.addView(backendUrlInput)
        root.addView(devUserInput)
        root.addView(sessionInput)

        val actions = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        actions.addView(button("Camera") { takePhoto.launch(null) })
        actions.addView(button("Photo") { pickImage.launch("image/*") })
        actions.addView(button("Submit") { submitText() })
        root.addView(actions)

        root.addView(statusView)
        root.addView(textInput)
        root.addView(responseView)

        setContentView(ScrollView(this).apply { addView(root) })
        setStatus("Ready")
    }

    private fun editText(hint: String, value: String, multiline: Boolean = false): EditText {
        return EditText(this).apply {
            this.hint = hint
            setText(value)
            inputType = if (multiline) {
                InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            } else {
                InputType.TYPE_CLASS_TEXT
            }
            minLines = if (multiline) 8 else 1
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
            )
        }
    }

    private fun button(label: String, onClick: () -> Unit): Button {
        return Button(this).apply {
            text = label
            setOnClickListener { onClick() }
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        }
    }

    private fun scanUri(uri: Uri) {
        setStatus("Loading image")
        try {
            val bitmap = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                ImageDecoder.decodeBitmap(ImageDecoder.createSource(contentResolver, uri))
            } else {
                @Suppress("DEPRECATION")
                MediaStore.Images.Media.getBitmap(contentResolver, uri)
            }
            scanBitmap(bitmap)
        } catch (error: Exception) {
            setStatus("Image load failed: ${error.message}")
        }
    }

    private fun scanBitmap(bitmap: Bitmap) {
        setStatus("Scanning")
        scanner.scan(
            bitmap = bitmap,
            onSuccess = { normalizedText ->
                textInput.setText(normalizedText)
                setStatus("Text extracted: ${normalizedText.length} chars")
            },
            onFailure = { error ->
                setStatus("Scan failed: ${error.message}")
            },
        )
    }

    private fun submitText() {
        val normalizedText = ScannerTextNormalizer.normalize(textInput.text.toString())
        val validationError = ScannerTextNormalizer.validationError(normalizedText)
        if (validationError != null) {
            setStatus(validationError)
            return
        }

        val idempotencyKey = ScannerTextNormalizer.stableIdempotencyKey(normalizedText)
        val suffix = UUID.randomUUID().toString().take(8)
        val payload = ContractAnalysisPayload(
            sessionId = sessionInput.text.toString().ifBlank { "session_mobile_text_scanner" },
            artifactLabel = "mobile-text-scanner-contract.txt",
            idempotencyKey = idempotencyKey,
            documentText = normalizedText,
            observationId = "obs_mobile_$suffix",
            correlationId = "corr_mobile_$suffix",
            traceId = "trace_mobile_$suffix",
        )

        setStatus("Submitting")
        Thread {
            try {
                val response = BackendClient.postContractAnalysis(
                    baseUrl = backendUrlInput.text.toString(),
                    payload = payload,
                    devUserId = devUserInput.text.toString(),
                )
                runOnUiThread {
                    responseView.text = response
                    setStatus("Submitted")
                }
            } catch (error: Exception) {
                runOnUiThread {
                    responseView.text = error.toString()
                    setStatus("Submit failed")
                }
            }
        }.start()
    }

    private fun setStatus(message: String) {
        statusView.text = message
    }
}
