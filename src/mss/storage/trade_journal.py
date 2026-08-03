"""
MSS Trade Journal
Version : 1.0
Sprint : 13.0
Compatible : v0.24
"""

import sqlite3

from mss.domain.trade_journal_entry import TradeJournalEntry


class TradeJournal:

    def __init__(

        self,

        database="trade_journal.db",

    ):

        self.database = database

        self._create_table()

    def _create_table(self):

        connection = sqlite3.connect(

            self.database,

        )

        cursor = connection.cursor()

        cursor.execute(

            """
            CREATE TABLE IF NOT EXISTS trade_journal(

                ticket INTEGER PRIMARY KEY,

                symbol TEXT,

                direction TEXT,

                volume REAL,

                entry_price REAL,

                exit_price REAL,

                stop_loss REAL,

                take_profit REAL,

                profit REAL,

                commission REAL,

                swap REAL,

                open_time TEXT,

                close_time TEXT,

                strategy TEXT,

                timeframe TEXT,

                comment TEXT

            )
            """

        )

        connection.commit()

        connection.close()

    def save(

        self,

        entry: TradeJournalEntry,

    ):

        if not entry.valid:

            return False

        connection = sqlite3.connect(

            self.database,

        )

        cursor = connection.cursor()

        cursor.execute(

            """
            INSERT OR REPLACE INTO trade_journal(

                ticket,

                symbol,

                direction,

                volume,

                entry_price,

                exit_price,

                stop_loss,

                take_profit,

                profit,

                commission,

                swap,

                open_time,

                close_time,

                strategy,

                timeframe,

                comment

            )

            VALUES(

                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?

            )
            """,

            (

                entry.ticket,

                entry.symbol,

                entry.direction,

                entry.volume,

                entry.entry_price,

                entry.exit_price,

                entry.stop_loss,

                entry.take_profit,

                entry.profit,

                entry.commission,

                entry.swap,

                str(entry.open_time),

                str(entry.close_time),

                entry.strategy,

                entry.timeframe,

                entry.comment,

            ),

        )

        connection.commit()

        connection.close()

        return True