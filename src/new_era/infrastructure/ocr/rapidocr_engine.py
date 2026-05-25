from __future__ import annotations

import base64
from dataclasses import dataclass, field
from io import BytesIO

import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

from new_era.application.ports import OCREngine
from new_era.domain.documents import OCRExtraction


@dataclass(slots=True)
class RapidOCRAdapter(OCREngine):
    engine: RapidOCR = field(default_factory=RapidOCR)

    def extract_text(self, image_base64: str) -> OCRExtraction:
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        image_array = np.array(image)
        ocr_result, _ = self.engine(image_array)

        if not ocr_result:
            return OCRExtraction(
                text="",
                confidence=0.0,
                line_count=0,
                engine_name="rapidocr",
            )

        lines: list[str] = []
        confidences: list[float] = []
        for entry in ocr_result:
            if len(entry) < 2:
                continue
            line_text = str(entry[1]).strip()
            if not line_text:
                continue
            lines.append(line_text)
            if len(entry) > 2:
                try:
                    confidences.append(float(entry[2]))
                except (TypeError, ValueError):
                    pass

        combined_text = " ".join(lines).strip()
        average_confidence = round(
            sum(confidences) / len(confidences),
            2,
        ) if confidences else 0.0
        return OCRExtraction(
            text=combined_text,
            confidence=average_confidence,
            line_count=len(lines),
            engine_name="rapidocr",
        )
