from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

from new_era.application.ports import OCREngine
from new_era.domain.documents import OCRExtraction


@dataclass(slots=True)
class RapidOCRAdapter(OCREngine):
    engine: RapidOCR = field(default_factory=RapidOCR)

    def extract_text(self, *, image_base64: str) -> OCRExtraction:
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_array = np.array(image)
        ocr_result, _ = self.engine(image_array)

        if not ocr_result:
            return OCRExtraction(
                text="",
                confidence=0.0,
                line_count=0,
                engine_name="rapidocr",
            )

        lines = [str(entry[1]).strip() for entry in ocr_result if entry[1]]
        confidences = [float(entry[2]) for entry in ocr_result if len(entry) > 2]
        combined_text = " ".join(line for line in lines if line)
        average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return OCRExtraction(
            text=combined_text.strip(),
            confidence=round(average_confidence, 2),
            line_count=len(lines),
            engine_name="rapidocr",
        )
