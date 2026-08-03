from datetime import datetime

from mss.domain.trade_journal_entry import TradeJournalEntry
from mss.storage.trade_journal import TradeJournal


def test_save_trade(tmp_path):

    db = tmp_path / "journal.db"

    journal = TradeJournal(

        database=str(db),

    )

    entry = TradeJournalEntry(

        ticket=1001,

        symbol="XAUUSD",

        direction="BUY",

        volume=0.20,

        entry_price=4048.20,

        exit_price=4058.20,

        stop_loss=4044.20,

        take_profit=4060.20,

        profit=200,

        commission=0,

        swap=0,

        open_time=datetime.now(),

        close_time=datetime.now(),

        strategy="MSS",

        timeframe="M5",

        comment="pytest",

        valid=True,

    )

    assert journal.save(entry)


def test_invalid_trade(tmp_path):

    db = tmp_path / "journal.db"

    journal = TradeJournal(

        database=str(db),

    )

    entry = TradeJournalEntry()

    assert journal.save(entry) is False


def test_database_created(tmp_path):

    db = tmp_path / "journal.db"

    TradeJournal(

        database=str(db),

    )

    assert db.exists()