"""Two-variable sensitivity tables (Phase 4): run the engine across an X×Y grid of two
assumption drivers and extract one output metric — the classic IRR-vs-exit-cap × cost-overrun
data table. Fast enough serially (a solve is <100ms)."""
from __future__ import annotations

import copy
from typing import Any

from .solve import solve


def _set_path(obj: Any, path: str, value: Any) -> None:
    """Set a dotted path that may include list indices, e.g. 'cost_lines.1.amount'."""
    keys = path.split(".")
    cur = obj
    for k in keys[:-1]:
        cur = cur[int(k)] if isinstance(cur, list) else cur[k]
    last = keys[-1]
    if isinstance(cur, list):
        cur[int(last)] = value
    else:
        cur[last] = value


def _get_metric(result: dict, metric: str) -> Any:
    cur: Any = result
    for k in metric.split("."):
        cur = cur.get(k) if isinstance(cur, dict) else None
        if cur is None:
            break
    return cur


def sensitivity(assumptions: dict, x_path: str, x_values: list[float],
                y_path: str, y_values: list[float],
                metric: str = "returns.equity_irr") -> dict:
    """Returns matrix[j][i] = metric solved with x_path=x_values[i], y_path=y_values[j]."""
    matrix: list[list[Any]] = []
    for yv in y_values:
        row = []
        for xv in x_values:
            a = copy.deepcopy(assumptions)
            _set_path(a, x_path, xv)
            _set_path(a, y_path, yv)
            try:
                row.append(_get_metric(solve(a), metric))
            except Exception:
                row.append(None)
        matrix.append(row)
    return {"metric": metric, "x_path": x_path, "x_values": x_values,
            "y_path": y_path, "y_values": y_values, "matrix": matrix}
