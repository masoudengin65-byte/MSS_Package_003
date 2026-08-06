"""Immutable, JSON-serializable market context captured for a paper trade."""

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class ContextSnapshot:
    """Value object whose payload cannot be changed after construction."""

    payload_json: str

    @classmethod
    def create(cls, values):
        return cls(json.dumps(values, sort_keys=True, separators=(",", ":"), default=str))

    def to_dict(self):
        return json.loads(self.payload_json)

    def get(self, key, default=None):
        return self.to_dict().get(key, default)

    def __getitem__(self, key):
        return self.to_dict()[key]

    def __setitem__(self, key, value):
        raise TypeError("ContextSnapshot is immutable")

