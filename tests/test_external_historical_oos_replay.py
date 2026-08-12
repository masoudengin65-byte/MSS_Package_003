from mss.analysis.external_historical_oos_replay import ExternalHistoricalOOSReplay as R


def test_direction_net_uses_only_closed_direction():
    rows=[{"status":"CLOSED","direction":"BUY","profit":10},{"status":"OPEN","direction":"BUY","profit":99},{"status":"CLOSED","direction":"SELL","profit":-3}]
    assert R.direction_net(rows,"BUY")==10
    assert R.direction_net(rows,"SELL")==-3


def test_confirmation_is_strict_all_pass():
    replay=R(); summary={"closed_trades":100,"expectancy":1,"average_r":0.1,"profit_factor":1.1,"risk_audit":{"maximum_realized_loss_percent":1.0}}
    boot={"available":True,"bootstrap_metrics":{"expectancy":{"ci_95":{"lower":0.1}},"mean_r":{"ci_95":{"lower":0.01}}}}
    trades=[{"status":"CLOSED","direction":"BUY","profit":1},{"status":"CLOSED","direction":"SELL","profit":1}]
    assert replay.confirmation(summary,trades,boot,boot,{"source":True})["all_pass"] is True
    summary["profit_factor"]=1
    assert replay.confirmation(summary,trades,boot,boot,{"source":True})["all_pass"] is False
