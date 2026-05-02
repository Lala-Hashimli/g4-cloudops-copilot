from __future__ import annotations

import logging
import sys
from typing import Iterable

from .safe_format import sanitize_text


class SecretMaskingFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str | None]) -> None:
        super().__init__()
        self._secrets = list(secrets)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_text(record.msg, self._secrets)
        if record.args:
            record.args = tuple(
                sanitize_text(arg, self._secrets) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True


def setup_logging(secrets: Iterable[str | None]) -> None:
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            handler.addFilter(SecretMaskingFilter(secrets))
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    masking_filter = SecretMaskingFilter(secrets)
    for handler in logging.getLogger().handlers:
        handler.addFilter(masking_filter)

    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
    logging.getLogger("azure.identity").setLevel(logging.WARNING)
