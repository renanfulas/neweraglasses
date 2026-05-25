from __future__ import annotations

from new_era.domain.documents import OCRExtraction


class OCREngine:
    def extract_text(self, image_base64: str) -> OCRExtraction:
        raise NotImplementedError
