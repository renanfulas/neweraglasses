from __future__ import annotations

from unittest import TestCase

from new_era.application.use_cases import PolicyRejectedError, PolicyRejection
from new_era.domain.events.redaction import ForbiddenMetadataError


class PolicyRejectionTest(TestCase):
    def test_serializes_stable_rejection_detail(self) -> None:
        rejection = PolicyRejection(
            code="session_active_job_limit_exceeded",
            message="Wait for an analysis to finish before sending another document.",
            reason="quota_exceeded",
            scope="session",
            limit=5,
            current=5,
            retryable=True,
            metadata={"source_type": "pwa_multipart_upload"},
        )

        self.assertEqual(
            rejection.to_dict(),
            {
                "code": "session_active_job_limit_exceeded",
                "message": "Wait for an analysis to finish before sending another document.",
                "reason": "quota_exceeded",
                "scope": "session",
                "retryable": True,
                "limit": 5,
                "current": 5,
                "metadata": {"source_type": "pwa_multipart_upload"},
            },
        )

    def test_rejects_forbidden_metadata_keys(self) -> None:
        with self.assertRaises(ForbiddenMetadataError):
            PolicyRejection(
                code="upload_rejected",
                message="Upload rejected.",
                reason="validation_failed",
                scope="upload",
                metadata={"document_text": "sensitive"},
            )

    def test_error_wraps_rejection(self) -> None:
        rejection = PolicyRejection(
            code="upload_payload_too_large",
            message="The file is above the local upload limit.",
            reason="payload_too_large",
            scope="upload",
            limit=7_500_000,
            retryable=False,
        )

        error = PolicyRejectedError(rejection)

        self.assertIs(error.rejection, rejection)
        self.assertEqual(str(error), "upload_payload_too_large")
