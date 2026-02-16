from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit

from scalpr_zen.data import load_cache
from scalpr_zen.gpu import compute_ema, find_signals, simulate_fills_gpu
from scalpr_zen.types import (
    BacktestResult,
    BacktestSummary,
    Direction,
    ExitReason,
    Fill,
    InstrumentSpec,
)


@dataclass(frozen=True)
class EngineConfig:
    instrument: InstrumentSpec
    tp_points: float
    sl_points: float
    fast_period: int
    slow_period: int
    cache_path: str


@njit(cache=True)
def filter_overlapping(
    signal_indices: np.ndarray,
    exit_indices: np.ndarray,
    signal_dirs: np.ndarray,
    exit_prices: np.ndarray,
    exit_reasons: np.ndarray,
    valid: np.ndarray,
) -> np.ndarray:
    n = len(signal_indices)
    keep = np.zeros(n, dtype=np.bool_)
    last_exit_idx = np.int64(-1)

    for i in range(n):
        if not valid[i]:
            continue
        if signal_indices[i] > last_exit_idx:
            keep[i] = True
            last_exit_idx = exit_indices[i]

    return keep


def _compute_summary(
    fills: list[Fill],
    total_ticks: int,
) -> BacktestSummary:
    if not fills:
        return BacktestSummary(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl_dollars=0.0,
            gross_profit=0.0,
            gross_loss=0.0,
            profit_factor=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            max_drawdown_dollars=0.0,
            max_consecutive_wins=0,
            max_consecutive_losses=0,
            total_ticks_processed=total_ticks,
        )

    wins = [f for f in fills if f.pnl_dollars > 0]
    losses = [f for f in fills if f.pnl_dollars <= 0]
    gross_profit = sum(f.pnl_dollars for f in wins)
    gross_loss = sum(f.pnl_dollars for f in losses)

    # Max drawdown
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for f in fills:
        equity += f.pnl_dollars
        if equity > peak:
            peak = equity
        dd = equity - peak
        if dd < max_dd:
            max_dd = dd

    # Consecutive streaks
    max_consec_w = 0
    max_consec_l = 0
    cur_w = 0
    cur_l = 0
    for f in fills:
        if f.pnl_dollars > 0:
            cur_w += 1
            cur_l = 0
        else:
            cur_l += 1
            cur_w = 0
        if cur_w > max_consec_w:
            max_consec_w = cur_w
        if cur_l > max_consec_l:
            max_consec_l = cur_l

    n_wins = len(wins)
    n_losses = len(losses)
    total = n_wins + n_losses

    return BacktestSummary(
        total_trades=total,
        winning_trades=n_wins,
        losing_trades=n_losses,
        win_rate=n_wins / total if total > 0 else 0.0,
        total_pnl_dollars=gross_profit + gross_loss,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=gross_profit / abs(gross_loss) if gross_loss != 0 else float("inf"),
        avg_win=gross_profit / n_wins if n_wins > 0 else 0.0,
        avg_loss=gross_loss / n_losses if n_losses > 0 else 0.0,
        max_drawdown_dollars=max_dd,
        max_consecutive_wins=max_consec_w,
        max_consecutive_losses=max_consec_l,
        total_ticks_processed=total_ticks,
    )


def run(config: EngineConfig) -> BacktestResult:
    params = {
        "instrument": f"{config.instrument.symbol} (E-mini Nasdaq 100)",
        "point_value": config.instrument.point_value,
        "tick_size": config.instrument.tick_size,
        "fast_ema": config.fast_period,
        "slow_ema": config.slow_period,
        "tp_points": config.tp_points,
        "sl_points": config.sl_points,
        "warmup_ticks": config.slow_period,
    }

    # 1. Load cached data
    try:
        prices, timestamps = load_cache(config.cache_path)
    except FileNotFoundError:
        return BacktestResult(
            success=False,
            error=f"Cache file not found: {config.cache_path}",
            strategy_name="EMA Crossover",
            params=params,
            fills=[],
            summary=None,
        )

    total_ticks = len(prices)
    if total_ticks == 0:
        return BacktestResult(
            success=False,
            error="Cache contains no data",
            strategy_name="EMA Crossover",
            params=params,
            fills=[],
            summary=None,
        )

    # Add data range to params
    from datetime import datetime, timezone

    first_ts = datetime.fromtimestamp(timestamps[0] / 1e9, tz=timezone.utc)
    last_ts = datetime.fromtimestamp(timestamps[-1] / 1e9, tz=timezone.utc)
    params["data_range"] = f"{first_ts.strftime('%Y-%m-%d')} to {last_ts.strftime('%Y-%m-%d')}"

    # 2. Compute EMAs
    fast_ema = compute_ema(prices, config.fast_period)
    slow_ema = compute_ema(prices, config.slow_period)

    # 3. Find crossover signals
    warmup = config.slow_period
    long_indices, short_indices = find_signals(fast_ema, slow_ema, warmup)

    if len(long_indices) == 0 and len(short_indices) == 0:
        summary = _compute_summary([], total_ticks)
        return BacktestResult(
            success=True,
            error=None,
            strategy_name="EMA Crossover",
            params=params,
            fills=[],
            summary=summary,
        )

    # 4. Merge and sort signals
    all_indices = np.concatenate([long_indices, short_indices])
    all_dirs = np.concatenate([
        np.ones(len(long_indices), dtype=np.int64),
        -np.ones(len(short_indices), dtype=np.int64),
    ])
    sort_order = np.argsort(all_indices)
    all_indices = all_indices[sort_order]
    all_dirs = all_dirs[sort_order]

    # 5. Simulate potential fills (parallel)
    exit_indices, exit_prices, exit_reasons, valid = simulate_fills_gpu(
        prices, timestamps, all_indices, all_dirs,
        config.tp_points, config.sl_points, config.instrument.tick_size,
    )

    # 6. Sequential overlap filter
    keep = filter_overlapping(
        all_indices, exit_indices, all_dirs,
        exit_prices, exit_reasons, valid,
    )

    # 7. Build Fill objects
    point_value = config.instrument.point_value
    fills: list[Fill] = []
    trade_num = 0
    for i in range(len(all_indices)):
        if not keep[i]:
            continue
        trade_num += 1
        entry_idx = all_indices[i]
        direction = Direction.LONG if all_dirs[i] == 1 else Direction.SHORT
        entry_price = float(prices[entry_idx])
        exit_price = float(exit_prices[i])
        exit_reason = ExitReason.TP if exit_reasons[i] == 0 else ExitReason.SL

        if direction == Direction.LONG:
            pnl_points = exit_price - entry_price
        else:
            pnl_points = entry_price - exit_price

        fills.append(Fill(
            trade_number=trade_num,
            direction=direction,
            entry_time=int(timestamps[entry_idx]),
            entry_price=entry_price,
            exit_time=int(timestamps[exit_indices[i]]),
            exit_price=exit_price,
            pnl_points=pnl_points,
            pnl_dollars=pnl_points * point_value,
            exit_reason=exit_reason,
        ))

    # 8. Compute summary
    summary = _compute_summary(fills, total_ticks)

    return BacktestResult(
        success=True,
        error=None,
        strategy_name="EMA Crossover",
        params=params,
        fills=fills,
        summary=summary,
    )
