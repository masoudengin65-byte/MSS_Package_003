"""Immutable diagnostic result value for Sprint 88 context combinations."""

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class ContextCombinationResult:
    """Stable serialized result for one pre-registered context pattern."""

    payload_json: str

    @classmethod
    def create(cls, values):
        return cls(json.dumps(values, sort_keys=True, separators=(",", ":"), default=str))

    def to_dict(self):
        return json.loads(self.payload_json)

    def __getitem__(self, key):
        return self.to_dict()[key]

    def __setitem__(self, key, value):
        raise TypeError("ContextCombinationResult is immutable")
