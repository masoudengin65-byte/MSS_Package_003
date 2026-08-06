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
        news_risk_status=None,
        portfolio_exposure=None,
    ) -> RiskProfile:

        profile = RiskProfile()

        profile.account_balance = balance
        profile.risk_percent = risk_percent
        profile.stop_distance = stop_distance

        if news_risk_status is not None:
            profile.trading_status = news_risk_status.trading_status

            if news_risk_status.trading_status in ("BLOCKED", "COOLDOWN"):
                profile.reason = (
                    f"News risk: {news_risk_status.trading_status} - "
                    f"{news_risk_status.next_event}"
                )
                return profile

        if portfolio_exposure is not None:
            profile.portfolio_risk_level = portfolio_exposure.risk_level
            profile.portfolio_risk_score = portfolio_exposure.portfolio_risk_score

            if portfolio_exposure.risk_level == "HIGH":
                profile.trading_status = "BLOCKED"
                profile.reason = (
                    "Portfolio risk: HIGH - "
                    f"score {portfolio_exposure.portfolio_risk_score}"
                )
                return profile

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
