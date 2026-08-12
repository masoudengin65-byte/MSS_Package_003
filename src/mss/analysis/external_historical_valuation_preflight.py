"""Validate historical account-currency conversion coverage before E.3 replay."""

from datetime import datetime

from mss.analysis.historical_valuation import HistoricalConversionPoint, HistoricalFxResolver


class ExternalHistoricalValuationPreflight:
    CONVERSION_SYMBOLS = {
        "JPY": "USDJPY", "CAD": "USDCAD", "CHF": "USDCHF", "GBP": "GBPUSD",
        "EUR": "EURUSD", "AUD": "AUDUSD", "NZD": "NZDUSD",
    }

    @classmethod
    def required_conversion_symbol(cls, profit_currency, account_currency="USD"):
        profit=str(profit_currency).upper(); account=str(account_currency).upper()
        if profit==account: return None
        if account!="USD" or profit not in cls.CONVERSION_SYMBOLS:
            raise ValueError(f"Unsupported conversion {profit}->{account}")
        return cls.CONVERSION_SYMBOLS[profit]

    @staticmethod
    def series(symbol, base, quote, candles):
        points=[HistoricalConversionPoint(candles[i+1].time,candles[i].close) for i in range(len(candles)-1)]
        return {symbol:(base,quote,points)}

    @classmethod
    def audit(cls, profit_currency, account_currency, target_candles, conversion_symbol=None,
              conversion_base=None, conversion_quote=None, conversion_candles=None,
              valuation_start_index=0):
        if not 0 <= valuation_start_index < len(target_candles):
            raise ValueError("valuation_start_index outside target candles")
        first_valuation_candle=target_candles[valuation_start_index]
        required=cls.required_conversion_symbol(profit_currency,account_currency)
        if required is None:
            return {"required":False,"path":"IDENTITY","coverage_complete":True,
                    "first_target_time":target_candles[0].time.isoformat(),
                    "first_valuation_time":first_valuation_candle.time.isoformat(),
                    "last_target_time":target_candles[-1].time.isoformat()}
        if conversion_symbol!=required or not conversion_candles:
            return {"required":True,"required_symbol":required,"coverage_complete":False,"reason":"CONVERSION_SERIES_MISSING"}
        resolver=HistoricalFxResolver(cls.series(conversion_symbol,conversion_base,conversion_quote,conversion_candles))
        initial=resolver.resolve(profit_currency,account_currency,target_candles[0].time)
        checks=[resolver.resolve(profit_currency,account_currency,first_valuation_candle.time),
                resolver.resolve(profit_currency,account_currency,target_candles[-1].time)]
        complete=all(x.available and x.rate_time<=x.requested_time for x in checks)
        return {"required":True,"required_symbol":required,"coverage_complete":complete,
                "first_target_time":target_candles[0].time.isoformat(),"last_target_time":target_candles[-1].time.isoformat(),
                "first_valuation_time":first_valuation_candle.time.isoformat(),
                "leading_target_conversion_available":initial.available,
                "first_conversion_time":checks[0].rate_time.isoformat() if checks[0].rate_time else None,
                "last_conversion_time":checks[-1].rate_time.isoformat() if checks[-1].rate_time else None,
                "path":checks[-1].path,"reason":None if complete else "CONVERSION_COVERAGE_INCOMPLETE"}
