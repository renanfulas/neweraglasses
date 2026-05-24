from __future__ import annotations

from typing import Protocol

from new_era.domain.documents import OCRExtraction


class OCREngine(Protocol):
    def extract_text(self, *, image_base64: str) -> OCRExtraction:
        raise NotImplementedError
