from datetime import datetime

from mss.analysis.smart_money_pipeline import SmartMoneyPipeline


class Candle:

    def __init__(self, high, low):

        self.high = high

        self.low = low

        self.open = low

        self.close = high

        self.time = datetime.now()


def build_candles():

    values = [

        (10, 5),
        (11, 6),
        (13, 7),
        (18, 8),
        (14, 7),
        (12, 6),
        (11, 5),
        (12, 4),
        (14, 5),
        (16, 6),
        (15, 7),

    ]

    return [

        Candle(high, low)

        for high, low in values

    ]


def test_pipeline_run():

    pipeline = SmartMoneyPipeline()

    result = pipeline.run(

        symbol="EURUSD",

        timeframe="M15",

        candles=build_candles(),

    )

    assert result.valid

    assert result.symbol == "EURUSD"

    assert result.timeframe == "M15"

    assert result.swing_count >= 2

    assert result.structure_state is not None

    assert result.recommendation in (

        "WAIT",

        "WATCH",

        "BUY",

    )


def test_pipeline_empty():

    pipeline = SmartMoneyPipeline()

    result = pipeline.run(

        symbol="EURUSD",

        timeframe="M15",

        candles=[],

    )

    assert result.valid

    assert result.swing_count == 0

    assert result.recommendation == "WAIT"


def test_pipeline_none():

    pipeline = SmartMoneyPipeline()

    result = pipeline.run(

        symbol="EURUSD",

        timeframe="M15",

        candles=None,

    )

    assert result.valid

    assert result.swing_count == 0

    assert result.recommendation == "WAIT"