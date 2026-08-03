"""
MSS Risk Engine
Version : 1.0
Sprint : 9.2
Compatible : v0.19
"""

from mss.domain.risk_profile import RiskProfile


class RiskEngine:

    CONTRACT_SIZE = 100000.0

    MIN_LOT = 0.01

    def calculate(
        self,
        balance: float,
        risk_percent: float,
        stop_distance: float,
    ) -> RiskProfile:

        profile = RiskProfile()

        profile.account_balance = balance
        profile.risk_percent = risk_percent
        profile.stop_distance = stop_distance

        if balance <= 0:
            return profile

        if risk_percent <= 0:
            return profile

        if stop_distance <= 0:
            return profile

        profile.risk_amount = (

            balance *

            risk_percent /

            100.0

        )

        profile.lot_size = (

            profile.risk_amount /

            (stop_distance * self.CONTRACT_SIZE)

        )

        if profile.lot_size < self.MIN_LOT:

            profile.lot_size = self.MIN_LOT

        profile.valid = True

        return profile