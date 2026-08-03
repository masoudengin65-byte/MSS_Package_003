from datetime import datetime

from mss.analysis.kill_zone_engine import KillZoneEngine


def test_london_open():

    zone = KillZoneEngine().detect(

        datetime(

            2026,

            1,

            1,

            8,

            30,

        )

    )

    assert zone.active

    assert zone.name == "LONDON_OPEN"

    assert zone.session == "LONDON"


def test_newyork_open():

    zone = KillZoneEngine().detect(

        datetime(

            2026,

            1,

            1,

            13,

            30,

        )

    )

    assert zone.active

    assert zone.name == "NEWYORK_OPEN"

    assert zone.session == "NEWYORK"


def test_newyork_close():

    zone = KillZoneEngine().detect(

        datetime(

            2026,

            1,

            1,

            19,

            0,

        )

    )

    assert zone.active

    assert zone.name == "NEWYORK_CLOSE"

    assert zone.session == "NEWYORK"


def test_no_kill_zone():

    zone = KillZoneEngine().detect(

        datetime(

            2026,

            1,

            1,

            22,

            0,

        )

    )

    assert not zone.active