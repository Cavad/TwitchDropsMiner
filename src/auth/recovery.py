"""Bounded retry rules for session reads and fresh proof validation."""

from __future__ import annotations

from src.auth.session_bundle import SessionError


class SessionRecovery:
    DELAYS = (1.0, 3.0)

    @staticmethod
    def retryable(error: SessionError) -> bool:
        diagnostic = error.diagnostic
        if error.code in {"AUTH", "IDENTITY", "ACCOUNT_MISMATCH", "STALE", "STOPPED", "FILE", "SAVE", "REPLAY", "FORMAT"}:
            return False
        if error.code == "CATALOG":
            return diagnostic.reason in {"integrity", "service", "headless_fallback"}
        if error.code in {"SDK_TIMEOUT", "CAPTURE_TIMEOUT"}:
            return True
        return error.code in {"REQUEST", "SDK_ISSUANCE", "HELPER_NETWORK"} and (
            diagnostic.reason in {"timeout", "connection", "dns", "service"}
            or diagnostic.upstream_status is not None and diagnostic.upstream_status >= 500
        )
