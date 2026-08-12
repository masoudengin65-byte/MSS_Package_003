from mss.analysis.external_historical_confirmatory_replay import ExternalHistoricalConfirmatoryReplay as R


def test_adjusted_bootstrap_is_deterministic():
    trades=[{"status":"CLOSED","canonical_symbol":"X","asset_class":"X","trade_id":i,"direction":"BUY","entry_time":str(i),"exit_time":str(i),"profit":1.0,"r_multiple":1.0} for i in range(20)]
    a=R.adjusted_bootstrap(trades,"ordinary",1-0.05/6,resamples=100)
    b=R.adjusted_bootstrap(trades,"ordinary",1-0.05/6,resamples=100)
    assert a==b
    assert a['expectancy']['interval']['lower']==1.0


def test_decision_requires_every_guardrail():
    summary={"closed_trades":100,"expectancy":1,"average_r":1,"profit_factor":2,"risk_audit":{"maximum_realized_loss_percent":1}}
    boot={"available":True,"expectancy":{"interval":{"lower":0.1}},"mean_r":{"interval":{"lower":0.1}}}
    trades=[{"status":"CLOSED","direction":"BUY","profit":1},{"status":"CLOSED","direction":"SELL","profit":1}]
    assert R.decide(summary,trades,boot,boot,{"source":True})['all_pass'] is True
    assert R.decide(summary,trades,boot,boot,{"source":False})['all_pass'] is False
