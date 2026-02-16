# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**scalpr_zen** — Hyperminimalist backtesting environment for scalping strategies on CME Globex futures. Every parameter visible, every result visible, no black boxes. Each backtest iteration produces a `.txt` report file.

Current version: **v0.1**

## Architecture Philosophy

- **Transparency over convenience.** All strategy parameters, entry/exit logic, and results must be human-readable at every step. No hidden defaults.
- **Plain text output.** Every backtest run writes a `.txt` file containing: full parameter set used, trade log, and summary statistics.
- **No framework dependencies for core logic.** The backtesting engine is pure Python — no pandas, no backtrader, no zipline for the simulation loop. Use only numpy for numerics and databento-dbn for data loading.
- **Config describes, code executes.** Strategy parameters live in config (dict or dataclass), never hardcoded in simulation functions.

## Market Data

Data lives in `data/` as Databento archives. Current dataset:

- **Source:** Databento GLBX.MDP3 (CME Globex)
- **Schema:** `trades` (tick-level trade prints)
- **Instrument:** `NQ.FUT` (Nasdaq 100 E-mini futures, all active contracts)
- **Format:** `.dbn.zst` (DBN v1, zstd compressed), one file per calendar day
- **Range:** 2025-02-16 through 2026-02-16 (~365 daily files)
- **Symbology:** `symbology.json` maps parent symbol `NQ.FUT` to individual contract instrument IDs (NQH5, NQM5, NQU5, NQZ5, NQH6, NQM6, etc.)

To load data, use `databento` Python package: `pip install databento`. The DBN files decode to `TradeMsg` records with fields: `ts_event`, `price`, `size`, `side`, `action`, `instrument_id`.

### Contract Rollover

The symbology file shows multiple NQ contracts active simultaneously. The front-month contract (highest volume) shifts quarterly. When backtesting continuous series, filter by the front-month instrument_id for each date range. Contract codes: H=Mar, M=Jun, U=Sep, Z=Dec.

## Instrument Specifications

- **MNQ** (Micro E-mini Nasdaq): tick size 0.25, tick value $0.50, point value $2.00
- **NQ** (E-mini Nasdaq): tick size 0.25, tick value $5.00, point value $20.00
- If both TP and SL are hit on the same bar/tick window, assume SL hit first (worst case)
- All prices must snap to valid tick increments (multiples of 0.25)

## Commands

```bash
# Install dependencies
pip install databento numpy

# Run backtest (once implemented)
python run_backtest.py

# Run tests
pytest tests/
```

## Output Convention

Each backtest iteration writes to `results/` with filename pattern:
```
results/{strategy_name}_{timestamp}.txt
```

The `.txt` file must contain (in plain text, not JSON):
1. Strategy name and version
2. Complete parameter set (every single parameter, no omissions)
3. Date range tested
4. Trade log: entry time, direction, entry price, exit time, exit price, P&L per trade
5. Summary: total trades, win rate, total P&L, max drawdown, profit factor

## Project Rules

- Strategy spec files (when they exist) are the **source of truth** — if code contradicts the spec, the spec wins.
- Return dataclasses from backtest functions, not raw dicts or tuples.
- Errors as values: backtest functions return a result object with success/failure status, not exceptions for expected failures like empty data or no trades.
