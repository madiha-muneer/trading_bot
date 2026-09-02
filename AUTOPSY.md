# BTC Sideways-Grid Program — Final Autopsy

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

# 2. Thesis 1 — Daily Timeframe

## 2.1 Claim

Bitcoin's daily sideways regimes might contain enough internal oscillation for a buy-side grid to earn small repeated profits while remaining protected from major losses by the regime detector.

The strategy therefore required sufficient income during normal sideways trading to compensate for the recurring losses caused by downward range breaks.

---

## 2.2 The Hurdle

Before testing the strategy, we set a minimum performance requirement:

> **+0.13% of deployed capital per active trading day.**

The strategy had to achieve this on **both** the training and validation periods.

The hurdle was based on the actual cost of sideways regimes breaking downward.

A **down-kill** means a downward break that forces the strategy to exit below the range floor.

From 23 observed regimes between 2019–2026:

* ~32% ended in a downward break
* Those exits cost ~7.5% of deployed capital on average
* An average regime provided ~19 tradable days

Therefore:

**0.32 × 7.5% ÷ 19 ≈ 0.13% per active day**

This means the grid needed to earn roughly 0.13% per active day during normal sideways trading to compensate for the losses caused by downward regime breaks.

A strategy that passed training but failed validation was rejected because it could be overfit.

The hurdle was subsequently audited for a gross-vs-net accounting issue. The calculation was corrected, and the final verdict remained unchanged.

---

## 2.3 What We Tested

The regime detector was **frozen before strategy testing began**.

Its 30-day window, hysteresis thresholds, and kill rules were not changed during the strategy experiments. We only changed the trading layer.

We tested:

### Ladder placement

* `band_bottom` — rungs start from the bottom of the frozen band
* `price_anchor` — rungs are placed below the price when the regime starts
* `full_band` — rungs are spread across the band

### Number of rungs

* 4
* 5
* 6
* 8

### Ramp

* **ON** — gradually deploy rungs
* **OFF** — deploy the allowed rungs immediately

### Re-anchoring

* No re-anchoring
* Re-anchor after 3 days without a buy
* Re-anchor after 5 days without a buy

The backtester used:

* **Daily candles** for regime detection and strategy decisions
* **1-minute candles** to determine whether orders actually filled during each day
* Trading **fees and slippage** in the fill simulation

We used chronological data splits:

* **Training:** 2019–2023
* **Validation:** 2024–2025
* **Final test:** 2026, kept completely untouched

The purpose was to find a strategy that worked not only on the data used to develop it, but also on later unseen data.

---

## 2.4 Results

### Best result

The best configuration was:

* Placement: `price_anchor`
* Rungs: 4
* Ramp: ON
* Re-anchor: OFF

|            |   Required |       Best Result |
| ---------- | ---------: | ----------------: |
| Train      | +0.13%/day | **+0.016%/day ❌** |
| Validation | +0.13%/day | **+0.040%/day ❌** |

It completed only **16 cycles** across seven years.

This is far below the **≥100-cycle significance requirement**. Therefore, even the small positive result cannot be treated as strong evidence of a real trading edge.

### Re-anchoring

Re-anchoring did not solve the problem.

| Re-anchor |       Train |  Validation |
| --------- | ----------: | ----------: |
| None      | +0.016%/day | +0.040%/day |
| 3 days    | +0.015%/day | +0.003%/day |
| 5 days    | +0.016%/day | +0.005%/day |

Re-anchoring therefore made the validation result worse.

### The important bookends

| Design                 | Result                                             |
| ---------------------- | -------------------------------------------------- |
| `band_bottom` baseline | **−33.6%** full-history return, **35.9% drawdown** |
| `price_anchor` / 4     | Best result: **+0.016% train, +0.040% validation** |
| `full_band` / 8        | **−0.083% train, −0.034% validation**              |

The `full_band` experiment produced much more trading activity (118–185 cycles), but still performed poorly.

This showed that simply making the bot trade more often did **not** solve the problem.

The extra fills also created more exposure to losses when the sideways regime broke.

---

## 2.5 Verdict

> **The daily BTC grid strategy is not viable.**

No tested variant reached the required **+0.13% per active day on both training and validation**.

The best configuration achieved only:

* **+0.016%/day** on training
* **+0.040%/day** on validation
* **16 completed cycles**

It also failed the ≥100-cycle significance requirement.

The experiments showed an important pattern:

> **Making the bot trade more did not create enough additional profit to compensate for the losses caused by regime breaks.**

### Decision

**Reject the daily strategy. Stop tuning it.**

The daily strategy thesis is closed.

---

# 3. Thesis 2 — 4H Timeframe

## 3.1 Claim

A shorter timeframe might improve the economics of the grid.

The hypothesis was that intraday ranges could provide a better **wiggle-to-kill ratio**, while a faster detector could reduce the damage caused by range breaks.

Moving from daily detection to 4H also gives a roughly **6× faster kill clock**.

If breakout losses were substantially caused by delayed detection, this could make the strategy viable.

---

## 3.2 Method

The same regime-detector concept was tested on **4H candles** using:

* Window: **W = 30**
* Same detector family
* Economics measured **before writing/testing strategy code**

This was a deliberate **stage-2 gate**.

The question was not:

> "Can we find a profitable grid?"

The question was:

> "Does the 4H regime itself have economics worth building a grid around?"

Two runs were pre-registered, with the decision gate written before observing any results:

| Economics                  | Decision                 |
| -------------------------- | ------------------------ |
| **≥ +0.13% / ON-day cost** | **FAIL**                 |
| **≤ +0.08% / ON-day cost** | **PROCEED**              |
| Between 0.08% and 0.13%    | Requires explicit review |

### Run 1 — Default ATR band

**0.393%/ON-day — FAIL**

### Run 2 — Halved ATR band

**0.344%/ON-day — FAIL**

The second configuration improved the economics slightly, but not remotely enough to cross the proceed threshold.

---

## 3.3 Why 4H Failed

The 4H timeframe did reduce regime lifetime substantially:

> **~19 days → ~6 days**

But the down-kill depth barely improved:

> **~5% → ~3.6%**

The mechanism is the important finding:

> **Breakout overshoot is impulse, not lag — the damage is inside the breakout candle itself, so exiting 4 hours sooner instead of a day sooner saves almost nothing.**

The shorter detection clock therefore did not remove the fundamental cost of range failure.

The regime simply became shorter-lived without becoming sufficiently safer.

---

## 3.4 Verdict

> **The 4H thesis fails at the economics gate.**

The measured cost was:

* **0.393%/ON-day** under the default ATR band
* **0.344%/ON-day** under the halved ATR band

Both are far above the **≤0.08%/ON-day proceed threshold**.

No strategy code was required.

### Cost of this thesis

**Zero strategy code. Approximately two evenings of work.**

This is an important success of the staged research pipeline:

> **The economics gate killed an unpromising thesis before strategy implementation consumed significant development time.**

The 4H thesis is closed.

---

# 4. The Family-Level Finding

The two theses together reveal the more important result.

The question is no longer:

> "Which grid configuration should we try?"

It is:

> **"Does changing timeframe create a viable economic window for this mechanism?"**

The answer is no.

## 4.1 The Gradient

The daily timeframe required approximately:

> **0.13%/day**

of grid income merely to compensate for the recurring cost of regime breakdowns.

But the tested daily grid could not generate sufficient income.

The 4H timeframe was substantially worse:

> **~0.35%/day**

of economic cost.

So moving to a smaller timeframe did not improve the problem.

It made it **strictly worse**.

The mechanical reason is now understood: shortening the detection clock does not materially eliminate breakout damage because the major overshoot occurs **inside the breakout candle itself**.

Therefore:

* **Daily:** the grid does not generate enough income.
* **4H:** the underlying regime economics are already too expensive.
* **Intermediate timeframes:** 12H and 8H are covered by interpolation.
* **Faster timeframes:** 1H and below are covered by extrapolation of the observed mechanism.

There is no reason to enumerate every possible timeframe when the observed relationship already closes the economic gap.

---

## 4.2 Program-Level Conclusion

> **At no tested or interpolated timeframe do BTC's calm ranges oscillate internally enough to pay trading fees plus the recurring cost of range breakdowns, for a buy-side grid.**

Daily fails on income.

Everything faster fails on cost.

**The gap never opens.**

---

## 4.3 Scope Limits

This conclusion is deliberately narrow.

It covers:

* **BTC/USDT**
* **2019–2026**
* This regime-detector family
* Buy-side grid / mean-reversion mechanics
* The tested daily and 4H timeframes
* Interpolation/extrapolation of the observed timeframe relationship

It does **not** prove that:

* other assets cannot work
* other market regimes cannot work
* momentum strategies cannot work
* breakout strategies cannot work
* different trading mechanisms cannot work
* future Bitcoin market structure cannot change

In fact, the overshoot evidence suggests that **breakout/momentum mechanics may be where the market's movement was actually paying**, rather than inside-range buy-side mean reversion.

An autopsy that overclaims is as bad as one that underclaims.

---

# 5. Process Record

The program was designed to close hypotheses rather than continuously tune them.

### Pre-registered gates

Both theses had explicit decision gates before the relevant results were used to make the decision:

* **Thesis 1:** `DECISION.md`
* **Thesis 2:** the **0.13% / 0.08% ON-day economic gate**

Both gates were honored on their first firing.

### Hurdle audit

The daily hurdle contained a **gross-vs-net accounting double-count**.

The calculation was audited, the error was corrected, and the final verdict **survived the correction**.

This matters because the objective was not to defend the original number; it was to verify whether the thesis survived an honest accounting correction.

### Report bug — aliased `current`

A report bug caused `current` state to be mutated through an aliased object, fabricating a **66-day phantom regime**.

The lesson: **state used for reporting must not share mutable references with state being advanced by the detector.**

### Report bug — `==` versus `=`

A separate bug came from confusing comparison (`==`) with assignment (`=`).

The lesson: **state-transition code must be tested explicitly so an intended assignment cannot silently become a comparison.**

These bugs were caught during the investigation rather than being allowed to influence the final thesis.

---

# 6. Assets and Reuse

The program leaves behind reusable research infrastructure:

### Data layer

* BTC/USDT **1-minute history**
* BTC/USDT **4H history**
* BTC/USDT **1D history**

### Regime detection

* Regime detector tested at **two timeframes**
* Frozen-band logic
* Hysteresis and kill rules

### Backtesting

* Fill-true backtester
* 1-minute execution simulation
* Fees and slippage
* Independent cash/inventory ledger
* Double-ledger reconciliation

### Research harness

* Parameter sweep framework
* Chronological train/validation discipline
* Untouched final-test period
* Automated detector/strategy testing
* Test suite

### Reusable BTC observations

Two empirical numbers should be preserved as inputs for future BTC research:

**Range-breakout overshoot:**

> approximately **2–4× ATR beyond the band**

**Break direction:**

> approximately **60% up / 40% down**

These numbers do not prove a future strategy, but they are useful empirical priors that future BTC theses can borrow without immediately re-measuring the same phenomenon.

---

# 7. Postscript

**Program closed 2026-09-02. Any future work on this asset must propose a different mechanism, not a different timeframe or parameter set.**

---

# Final Statement

The strategy failed.

The timeframe did not rescue it.

The parameter search did not rescue it.

The faster detector did not rescue it.

And the economic gate showed that continuing to search would not be research — it would be moving the search space after the evidence had already closed it.

> **The strategy failed. The experiment did not.**