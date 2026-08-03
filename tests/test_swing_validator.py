from datetime import datetime

from mss.analysis.swing_detector import Swing
from mss.analysis.swing_validator import SwingValidator


def test_validator():

    swings = [

        Swing(
            1,
            "LOW",
            100,
            datetime.now(),
        ),

        Swing(
            2,
            "HIGH",
            100.3,
            datetime.now(),
        ),

        Swing(
            8,
            "HIGH",
            104,
            datetime.now(),
        ),

    ]

    validator = SwingValidator()

    result = validator.validate(swings)

    assert len(result) == 2