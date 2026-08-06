"""Calculate portfolio exposure and overlap risk from open paper positions."""

from itertools import combinations

from mss.domain.portfolio_exposure import PortfolioExposure


class PortfolioExposureEngine:

    CURRENCIES = {
        "AUD", "CAD", "CHF", "CNY", "EUR", "GBP", "HKD",
        "JPY", "NZD", "SGD", "TRY", "USD", "ZAR",
    }

    def calculate(self, positions) -> PortfolioExposure:
        result = PortfolioExposure()
        open_positions = [
            position
            for position in (positions or [])
            if getattr(position, "valid", False)
            and getattr(position, "status", "") == "OPEN"
            and getattr(position, "volume", 0.0) > 0
        ]

        result.open_positions = len(open_positions)
        result.portfolio_exposure = round(
            sum(abs(position.volume) for position in open_positions),
            4,
        )

        legs = []
        for position in open_positions:
            direction = 1.0 if position.direction.upper() == "BUY" else -1.0
            signed_volume = direction * position.volume
            symbol = position.symbol.upper()

            result.asset_exposure[symbol] = round(
                result.asset_exposure.get(symbol, 0.0) + signed_volume,
                4,
            )

            position_legs = self._currency_legs(symbol, signed_volume)
            legs.append(position_legs)
            for currency, exposure in position_legs.items():
                if currency not in self.CURRENCIES:
                    continue
                result.currency_exposure[currency] = round(
                    result.currency_exposure.get(currency, 0.0) + exposure,
                    4,
                )

        result.correlation_percent = self._correlation_percent(legs)
        result.correlation_level = self._level(
            result.correlation_percent,
            medium=34.0,
            high=67.0,
        )
        result.portfolio_risk_score = self._risk_score(result)
        result.risk_level = self._level(
            result.portfolio_risk_score,
            medium=30.0,
            high=60.0,
        )
        result.valid = True
        return result

    def _currency_legs(self, symbol, signed_volume):
        root = "".join(character for character in symbol if character.isalpha())[:6]
        if len(root) != 6:
            return {}

        return {
            root[:3]: signed_volume,
            root[3:]: -signed_volume,
        }

    @staticmethod
    def _correlation_percent(legs):
        pairs = list(combinations(legs, 2))
        if not pairs:
            return 0.0

        correlated = 0
        for left, right in pairs:
            shared = set(left).intersection(right)
            if any(left[key] * right[key] > 0 for key in shared):
                correlated += 1

        return round(correlated / len(pairs) * 100.0, 2)

    @staticmethod
    def _risk_score(result):
        count = result.open_positions
        diversification = min(1.0, max(0, count - 1) / 2.0)
        volume_score = min(30.0, result.portfolio_exposure / 5.0 * 30.0)

        currency_values = [
            abs(value) for value in result.currency_exposure.values()
        ]
        currency_score = (
            max(currency_values) / sum(currency_values) * 20.0 * diversification
            if sum(currency_values) > 0
            else 0.0
        )

        asset_values = [abs(value) for value in result.asset_exposure.values()]
        asset_score = (
            max(asset_values) / sum(asset_values) * 20.0 * diversification
            if sum(asset_values) > 0
            else 0.0
        )
        correlation_score = result.correlation_percent / 100.0 * 30.0

        return round(
            min(100.0, volume_score + currency_score + asset_score + correlation_score),
            2,
        )

    @staticmethod
    def _level(value, medium, high):
        if value >= high:
            return "HIGH"
        if value >= medium:
            return "MEDIUM"
        return "LOW"
