"""One-time: read all DBN files -> save as cached .npz for fast backtest loading."""

import time

from scalpr_zen.data import preprocess_to_cache
from scalpr_zen.types import ContractPeriod

# ═══════════════════════════════════════════════════════
# PARAMETERS
# ═══════════════════════════════════════════════════════
DATA_DIR = "data/GLBX-20260216-EMA5CB8W6B"
CACHE_PATH = "cache/nq_ticks.npz"
START_DATE = "2025-02-18"
END_DATE = "2026-02-14"

ROLLOVER_SCHEDULE = [
    ContractPeriod("NQH5", "42288528", "2025-02-18", "2025-03-14"),
    ContractPeriod("NQM5", "42005804", "2025-03-14", "2025-06-13"),
    ContractPeriod("NQU5", "42008487", "2025-06-13", "2025-09-12"),
    ContractPeriod("NQZ5", "158704",   "2025-09-12", "2025-12-12"),
    ContractPeriod("NQH6", "42002475", "2025-12-12", "2026-02-14"),
]
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"Preprocessing DBN files from {DATA_DIR}")
    print(f"Date range: {START_DATE} to {END_DATE}")
    print(f"Output: {CACHE_PATH}")
    print()

    t0 = time.perf_counter()
    total_ticks = preprocess_to_cache(
        data_dir=DATA_DIR,
        cache_path=CACHE_PATH,
        schedule=ROLLOVER_SCHEDULE,
        start_date=START_DATE,
        end_date=END_DATE,
    )
    elapsed = time.perf_counter() - t0

    print()
    print(f"Done. {total_ticks:,} ticks cached in {elapsed:.1f}s")
    print(f"Cache file: {CACHE_PATH}")
