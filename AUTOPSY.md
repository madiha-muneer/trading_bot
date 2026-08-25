# Daily BTC Grid Strategy — Autopsy

## 1. The Idea

The goal was to trade Bitcoin only when the market was moving sideways inside a stable range.

A regime detector identified these sideways periods. When a sideways regime started, the detector froze the price band and the grid strategy created buy levels ("rungs") below the current price.

When price dropped to a rung, the bot bought BTC. It then placed a sell order one step higher. If price recovered, the position was sold for a small profit.

The basic idea was:

> Buy dips during calm sideways markets, sell the recovery, and stop trading when the sideways regime breaks.

The detector decided **when to trade**.  
The grid decided **how to trade**.

The strategy was designed to avoid chasing rising prices and to keep purchases relatively low so that a downward breakout would not leave the bot heavily exposed.

---

## 2. The Hurdle

Before testing the strategy, we set a minimum performance requirement:

> **+0.13% of deployed capital per active trading day.**

The strategy had to achieve this on **both** the training and validation periods.

The hurdle was based on the actual cost of sideways regimes breaking downward.

A **down-kill** means a downward break that forces the strategy to exit below the range floor.

From 23 observed regimes between 2019–2026:

- ~32% ended in a downward break
- Those exits cost ~7.5% of deployed capital on average
- An average regime provided ~19 tradable days

Therefore:

**0.32 × 7.5% ÷ 19 ≈ 0.13% per active day**

This means the grid needed to earn roughly 0.13% per active day during normal sideways trading to compensate for the losses caused by downward regime breaks.

A strategy that passed training but failed validation was also rejected because it could be overfit.

---

## 3. What We Tested

The regime detector was **frozen before strategy testing began**.

Its 30-day window, hysteresis thresholds, and kill rules were not changed during the strategy experiments. We only changed the trading layer.

We tested:

### Ladder placement

- `band_bottom` — rungs start from the bottom of the frozen band
- `price_anchor` — rungs are placed below the price when the regime starts
- `full_band` — rungs are spread across the band

### Number of rungs

- 4
- 5
- 6
- 8

### Ramp

- **ON** — gradually deploy rungs
- **OFF** — deploy the allowed rungs immediately

### Re-anchoring

- No re-anchoring
- Re-anchor after 3 days without a buy
- Re-anchor after 5 days without a buy

The backtester used:

- **Daily candles** for regime detection and strategy decisions
- **1-minute candles** to determine whether orders actually filled during each day
- Trading **fees and slippage** in the fill simulation

We used chronological data splits:

- **Training:** 2019–2023
- **Validation:** 2024–2025
- **Final test:** 2026, kept completely untouched

The purpose was to find a strategy that worked not only on the data used to develop it, but also on later unseen data.

---

## 4. Results

### Best result

The best configuration was:

- Placement: `price_anchor`
- Rungs: 4
- Ramp: ON
- Re-anchor: OFF

Results:

| | Required | Best Result |
|---|---:|---:|
| Train | +0.13%/day | **+0.016%/day ❌** |
| Validation | +0.13%/day | **+0.040%/day ❌** |

It completed only **16 cycles** across seven years.

This is far below our **≥100-cycle significance requirement**. Therefore, even the small positive result cannot be treated as strong evidence of a real trading edge.

### Re-anchoring

Re-anchoring did not solve the problem.

For 4 rungs:

| Re-anchor | Train | Validation |
|---|---:|---:|
| None | +0.016%/day | +0.040%/day |
| 3 days | +0.015%/day | +0.003%/day |
| 5 days | +0.016%/day | +0.005%/day |

Re-anchoring therefore made the validation result worse.

### The important bookends

| Design | Result |
|---|---|
| `band_bottom` baseline | **−33.6%** full-history return, **35.9% drawdown** |
| `price_anchor` / 4 | Best result: **+0.016% train, +0.040% validation** |
| `full_band` / 8 | **−0.083% train, −0.034% validation** |

The `full_band` experiment is especially important because it produced much more trading activity (118–185 cycles), but it still performed poorly.

This showed that simply making the bot trade more often did **not** solve the problem.

The extra fills also created more exposure to losses when the sideways regime broke.

---

## 5. Verdict

> **The daily BTC grid strategy is not viable.**

No tested variant reached the required **+0.13% per active day on both training and validation**.

The best configuration achieved only:

- **+0.016%/day** on training
- **+0.040%/day** on validation
- **16 completed cycles**

It also failed the ≥100-cycle significance requirement.

The experiments showed an important pattern:

> **Making the bot trade more did not create enough additional profit to compensate for the losses caused by regime breaks.**

The strategy therefore failed its predefined requirements.

### Decision

**Reject the daily strategy. Stop tuning it.**

The investigation is closed.

---

## 6. What Survives This Verdict

This verdict is specifically about **grid strategies trading BTC inside daily-detected sideways ranges**.

It does **not** prove that:

- intraday-detected ranges cannot work
- another timeframe cannot work
- another asset cannot work
- another trading strategy cannot work

Those are separate hypotheses and would need separate tests.

The infrastructure built during this project remains useful:

- market-data pipeline
- regime detector
- frozen-band logic
- 1-minute fill simulation
- backtester
- strategy framework
- sweep framework
- test suite

The daily strategy failed, but the **research infrastructure succeeded**. It allowed us to test the idea, measure the risks, reject weak variants, and close the investigation without moving the goalposts.

> **The strategy failed. The experiment did not.**_