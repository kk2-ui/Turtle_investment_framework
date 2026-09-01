"""Strategy services package — grid trading, MTH (满堂红), staged buy.

Each module ports a specific Android strategy:
- grid: GridCycleRecord CRUD + buy/sell cycle tracking
- mth: 满堂红 cycle state management
"""

from niangao.services.strategies.grid import (  # noqa: F401
    record_grid_sell,
    record_grid_buy,
    list_open_cycles,
    list_cycles,
    get_cycle,
    delete_cycle,
    grid_summary,
    GridCycleResult,
    GridBuyResult,
)

from niangao.services.strategies.mth import (  # noqa: F401
    enable_mth,
    disable_mth,
    advance_mth_cycle,
    reset_mth_cycle,
    get_mth_status,
    list_mth_stocks,
)

from niangao.services.strategies.staged import (  # noqa: F401
    generate_plan,
    get_plan,
    mark_level,
    delete_plan,
    list_active_plans,
)
