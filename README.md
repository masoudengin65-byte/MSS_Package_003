# MSS Personal Edition v1.0

Integrated MT5 market analysis, paper trading, risk controls, performance
analysis, adaptive strategy optimization, dashboard output, and Excel journal.

Run the dashboard:

```powershell
$env:PYTHONPATH='src'
python -m mss
```

Run verification:

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests integration_tests/test_personal_edition_v1.py
```

Live candle analysis requires the connected MT5 terminal to have synchronized
history for the configured symbol and timeframes.
