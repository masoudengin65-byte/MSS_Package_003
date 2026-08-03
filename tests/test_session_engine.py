from datetime import datetime

from mss.analysis.session_engine import SessionEngine


def test_asia_session():

    session = SessionEngine().detect(

        datetime(

            2026,

            1,

            1,

            2,

            0,

        )

    )

    assert session.active

    assert session.name == "ASIA"


def test_london_session():

    session = SessionEngine().detect(

        datetime(

            2026,

            1,

            1,

            10,

            0,

        )

    )

    assert session.active

    assert session.name == "LONDON"


def test_newyork_session():

    session = SessionEngine().detect(

        datetime(

            2026,

            1,

            1,

            15,

            0,

        )

    )

    assert session.active

    assert session.name == "NEWYORK"


def test_no_session():

    session = SessionEngine().detect(

        datetime(

            2026,

            1,

            1,

            22,

            30,

        )

    )

    assert not session.active