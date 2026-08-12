from datetime import datetime,timedelta
import pytest
from mss.analysis.external_historical_valuation_preflight import ExternalHistoricalValuationPreflight as P
from mss.domain.candle import Candle

def candles(n=3):
    t=datetime(2020,1,1); return [Candle(time=t+timedelta(minutes=15*i),open=100,high=101,low=99,close=100+i,tick_volume=1,spread=1,real_volume=0) for i in range(n)]
def test_required_conversion_mapping():
    assert P.required_conversion_symbol('JPY')=='USDJPY'; assert P.required_conversion_symbol('USD') is None
    with pytest.raises(ValueError): P.required_conversion_symbol('SEK')
def test_identity_is_complete(): assert P.audit('USD','USD',candles())['coverage_complete'] is True
def test_inverse_conversion_has_no_lookahead():
    conversion_candles=candles(5)
    target_candles=conversion_candles[2:]
    r=P.audit('JPY','USD',target_candles,'USDJPY','USD','JPY',conversion_candles)
    assert r['coverage_complete'] is True
    assert r['path'].endswith('INVERSE')
def test_warmup_makes_leading_conversion_gap_non_actionable():
    target=candles(5)
    r=P.audit('JPY','USD',target,'USDJPY','USD','JPY',target,2)
    assert r['leading_target_conversion_available'] is False
    assert r['coverage_complete'] is True
