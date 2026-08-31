from __future__ import annotations

import numpy as np

import mss.analysis.sprint93_paired_forward_activation as activation


def test_rate_value_supports_mt5_numpy_structured_row():
    row = np.array(
        [
            (
                1_787_500_000,
                100.0,
                101.0,
                99.0,
                100.5,
                42,
                3,
                7,
            )
        ],
        dtype=[
            ("time", "i8"),
            ("open", "f8"),
            ("high", "f8"),
            ("low", "f8"),
            ("close", "f8"),
            ("tick_volume", "i8"),
            ("spread", "i8"),
            ("real_volume", "i8"),
        ],
    )[0]

    assert isinstance(row, np.void)
    assert activation._rate_value(row, "time") == 1_787_500_000
    assert activation._rate_value(row, "close") == 100.5
