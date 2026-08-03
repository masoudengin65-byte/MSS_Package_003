from datetime import datetime

from mss.analysis.market_analyzer import MarketAnalyzer
from mss.domain.market_context import MarketContext
from mss.domain.replay_candle import ReplayCandle


def test_market_analyzer_returns_result():

    candle = ReplayCandle(

        time=datetime.now(),

        open=100,

        high=105,

        low=99,

        close=104,

    )

    context = MarketContext(

        symbol="XAUUSD",

        timeframe="M1",

        candles=[candle],

        swings=[],

        last_closed_candle=candle,

    )

    result = MarketAnalyzer().analyze(

        context,

    )

    assert result.symbol == "XAUUSD"

    assert result.timeframe == "M1"


def test_market_analyzer_none():

    result = MarketAnalyzer().analyze(

        None,

    )

    assert result.symbol == ""

    assert result.timeframe is None