import base64
import io
from unittest import TestCase

from PIL import Image, ImageDraw, ImageFont

from new_era.infrastructure.ocr import RapidOCRAdapter


class RapidOCRAdapterTest(TestCase):
    def test_extracts_text_from_generated_image(self) -> None:
        image = Image.new("RGB", (1200, 240), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=48)
        draw.text(
            (40, 80),
            "AUTOMATIC RENEWAL CANCELLATION FEE",
            fill="black",
            font=font,
        )
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")

        extraction = RapidOCRAdapter().extract_text(image_base64=image_base64)

        self.assertIn("AUTOMATIC RENEWAL", extraction.text)
        self.assertGreater(extraction.confidence, 0.5)
        self.assertGreaterEqual(extraction.line_count, 1)
