from datetime import datetime

from mss.analysis.replay_engine import ReplayEngine
from mss.domain.replay_candle import ReplayCandle


def build_candles():

    return [

        ReplayCandle(
            time=datetime.now(),
            open=100,
            high=105,
            low=99,
            close=104,
        ),

        ReplayCandle(
            time=datetime.now(),
            open=104,
            high=107,
            low=103,
            close=106,
        ),

        ReplayCandle(
            time=datetime.now(),
            open=106,
            high=108,
            low=105,
            close=107,
        ),

    ]


def test_replay_processes_all_candles():

    result = ReplayEngine().replay(

        build_candles(),

    )

    assert result.completed

    assert result.processed_candles == 3

    assert result.elapsed_seconds >= 0


def test_replay_empty():

    result = ReplayEngine().replay([])

    assert result.completed

    assert result.processed_candles == 0

    assert isinstance(result.orders, list)

    assert isinstance(result.positions, list)


def test_replay_none():

    result = ReplayEngine().replay(None)

    assert not result.completed

    assert result.processed_candles == 0

    assert isinstance(result.orders, list)

    assert isinstance(result.positions, list)