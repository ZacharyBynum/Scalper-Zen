from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmaCrossConfig:
    fast_period: int
    slow_period: int

    @property
    def warmup_ticks(self) -> int:
        return self.slow_period
