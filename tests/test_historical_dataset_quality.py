from mss.analysis.historical_dataset_quality import audit_rows


def row(t, eligible=True):
    return dict(time=t,open=10.,high=11.,low=9.,close=10.,spread=1,
                tick_volume=10,real_volume=0,performance_eligible=eligible)


def test_exact_window_warmup_and_trailing_gap():
    result = audit_rows([row(0,False),row(900),row(1800)],900,3600,warmup=1)
    assert result['integrity_pass']
    assert result['performance_rows']==2 and result['trailing_missing_slots']==1
    assert result['zero_counts_performance_only']['real_volume']==2


def test_duplicate_future_and_flag_fail():
    result = audit_rows([row(0,False),row(900),row(900),row(1800)],900,1800,warmup=1)
    assert result['integrity_errors']['duplicate_timestamp']==1
    assert result['integrity_errors']['at_or_after_exclusive_end']==1
    assert result['integrity_errors']['eligibility_mismatch']==1


def test_internal_gap_is_unverified_not_imputed():
    result = audit_rows([row(0,False),row(900),row(2700)],900,3600,warmup=1)
    assert result['internal_missing_slots']==1
    assert result['largest_gaps'][0]['closure_status']=='UNVERIFIED'
    assert result['row_count']==3


def test_invalid_numeric_types_and_prices():
    bad=row(900); bad['spread']=True; bad['open']=float('nan')
    result=audit_rows([row(0,False),bad],900,1800,warmup=1)
    assert result['integrity_errors']['invalid_spread']==1
    assert result['integrity_errors']['invalid_price']==1
