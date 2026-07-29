"""Centralized JSON serialization with UUID and datetime support."""

import json
from datetime import date, datetime
from typing import Any
from uuid import UUID


class SwxJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, UUID):
            return str(o)
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return super().default(o)


def dumps(obj: Any, **kwargs: Any) -> str:
    kwargs.setdefault("cls", SwxJSONEncoder)
    return json.dumps(obj, **kwargs)


def loads(s: str | bytes, **kwargs: Any) -> Any:
    return json.loads(s, **kwargs)