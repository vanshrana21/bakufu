# Rainfall Regressor: Null Result

We pre-registered the hypothesis that observed lagged rainfall would
improve short-horizon forecasts, tested it with 25 paired backtest
origins at h=1, and found no effect (delta 0.13 pp MAPE, 95% CI ±0.44
pp, p = 0.409).

Consistent with residual diagnostic (p = 0.454 on monsoon vs
non-monsoon residuals). Prophet's yearly seasonality already absorbs
the monsoon signal in the aggregated MH+MP series.

A per-mine model might benefit from rainfall; publicly-available data
is only aggregated to state level.

## Design note on horizon scope

Observed lagged rainfall is only available at h=1 (one-month forecast).
At h≥2, lagged rainfall refers to months that haven't happened yet, so
the design necessarily falls back to climatology — which duplicates
Prophet's yearly seasonality. This test therefore evaluates rainfall's
marginal value at 1-month horizon only.

## Related follow-up

Rainfall is separately tested as a feature in the shortfall classifier
(Phase 3.2d), on the reasoning that a null on level forecasting does
not imply a null on deviation detection — those are different targets.
