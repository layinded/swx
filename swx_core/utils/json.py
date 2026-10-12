"""Centralized JSON serialization with UUID, datetime, and safe fallback support."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Union
from uuid import UUID


class SwxJSONEncoder(json.JSONEncoder):
    def default(self, o: object) -> Union[str, list[Any]]:  # type: ignore[override]
        """Serialize non-JSON-native types safely.

        Handles UUID, datetime, date, bytes, set, and falls back to str()
        for any other type — never raises TypeError.
        """
        if isinstance(o, UUID):
            return str(o)
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, bytes):
            return o.decode("utf-8", errors="replace")
        if isinstance(o, set):
            return list(o)
        return str(o)


def dumps(obj: Any, **kwargs: Any) -> str:
    kwargs.setdefault("cls", SwxJSONEncoder)
    return json.dumps(obj, **kwargs)


def loads(s: str | bytes, **kwargs: Any) -> Any:
    return json.loads(s, **kwargs)