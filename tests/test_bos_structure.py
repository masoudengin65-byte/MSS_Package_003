from datetime import datetime

from mss.analysis.swing_detector import Swing


def test_market_structure():

    swings = [

        Swing(1,"LOW",90,datetime.now()),

        Swing(2,"HIGH",100,datetime.now()),

        Swing(3,"LOW",95,datetime.now()),

        Swing(4,"HIGH",105,datetime.now()),

    ]

    assert swings[2].price > swings[0].price

    assert swings[3].price > swings[1].price