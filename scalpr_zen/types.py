from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Direction(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class ExitReason(Enum):
    TP = "TP"
    SL = "SL"


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    tick_size: float
    point_value: float


@dataclass(frozen=True)
class ContractPeriod:
    symbol: str
    instrument_id: str
    start_date: str
    end_date: str


@dataclass(frozen=True)
class Fill:
    trade_number: int
    direction: Direction
    entry_time: int
    entry_price: float
    exit_time: int
    exit_price: float
    pnl_points: float
    pnl_dollars: float
    exit_reason: ExitReason


@dataclass(frozen=True)
class BacktestSummary:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl_dollars: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    max_drawdown_dollars: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    total_ticks_processed: int


@dataclass(frozen=True)
class BacktestResult:
    success: bool
    error: str | None
    strategy_name: str
    params: dict[str, object]
    fills: list[Fill]
    summary: BacktestSummary | None


def snap_to_tick(price: float, tick_size: float = 0.25) -> float:
    return round(round(price / tick_size) * tick_size, 10)
