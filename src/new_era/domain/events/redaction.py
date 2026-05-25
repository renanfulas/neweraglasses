from __future__ import annotations

from collections.abc import Mapping


FORBIDDEN_METADATA_KEYS = {
    "access_token",
    "api_key",
    "camera_frame",
    "document_text",
    "full_ocr_text",
    "password",
    "raw_camera_frame",
    "raw_document_text",
    "secret",
    "token",
}


class ForbiddenMetadataError(ValueError):
    pass


def validate_event_metadata(metadata: Mapping[str, object]) -> None:
    forbidden = FORBIDDEN_METADATA_KEYS.intersection(metadata.keys())
    if forbidden:
        keys = ", ".join(sorted(forbidden))
        raise ForbiddenMetadataError(f"forbidden event metadata keys: {keys}")
