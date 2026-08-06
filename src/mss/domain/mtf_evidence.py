"""Immutable diagnostic-only multi-timeframe evidence for Sprint 86."""

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class MTFEvidence:
    """Stable JSON value object that cannot be consumed as mutable state."""

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
        raise TypeError("MTFEvidence is immutable")
