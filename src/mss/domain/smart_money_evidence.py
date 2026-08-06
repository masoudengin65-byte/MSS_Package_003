"""Immutable diagnostic-only Smart Money lifecycle evidence for Sprint 87."""

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class SmartMoneyEvidence:
    """Stable JSON snapshot that cannot be mutated after extraction."""

    payload_json: str

    @classmethod
    def create(cls, values):
        return cls(json.dumps(values, sort_keys=True, separators=(",", ":"), default=str))

    def to_dict(self):
        return json.loads(self.payload_json)

    def __getitem__(self, key):
        return self.to_dict()[key]

    def get(self, key, default=None):
        return self.to_dict().get(key, default)

    def __setitem__(self, key, value):
        raise TypeError("SmartMoneyEvidence is immutable")
