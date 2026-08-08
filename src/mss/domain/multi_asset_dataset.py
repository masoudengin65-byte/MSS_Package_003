"""Immutable diagnostic multi-asset historical dataset snapshot."""

from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class MultiAssetDataset:
    """Stable serialized dataset that cannot expose mutable internal state."""

    payload_json: str

    @classmethod
    def create(cls, values):
        return cls(json.dumps(
            values,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
            allow_nan=False,
        ))

    @property
    def sha256(self):
        return hashlib.sha256(self.payload_json.encode("utf-8")).hexdigest()

    def to_dict(self):
        return json.loads(self.payload_json)

    def __getitem__(self, key):
        return self.to_dict()[key]

    def get(self, key, default=None):
        return self.to_dict().get(key, default)

    def __setitem__(self, key, value):
        raise TypeError("MultiAssetDataset is immutable")
