"""Load-shifting LP (OR-Tools GLOP).
min  sum_t tariff_t*grid_t + lambda*waste_t  + mu*Pmax
s.t. grid_t >= base_t + flex_t - solar_t ; waste_t >= solar_t - base_t - flex_t ; grid_t,waste_t >= 0
     sum_{t in window_j} x_jt = E_j ; 0 <= x_jt <= cap_j ; x_jt = 0 outside window
     Pmax >= grid_t
Essential loads are never decision variables; they stay in base_kw. Recommendation mode only."""
from ortools.linear_solver import pywraplp


def _grid(base, flex, solar):
    return [max(0.0, base[t] + flex[t] - solar[t]) for t in range(len(base))]


def optimize_load_shifting(base_kw, solar_kw, tariff, flex_loads, waste_lambda=0.5, peak_penalty=0.0,
                           peak_cap_kw=None):
    T = len(base_kw)
    assert len(solar_kw) == T and len(tariff) == T
    s = pywraplp.Solver.CreateSolver("GLOP")
    x = {}
    for j, f in enumerate(flex_loads):
        lo, hi = f["window"]
        for t in range(T):
            ub = f["max_kw"] if lo <= t < hi else 0.0
            x[j, t] = s.NumVar(0, ub, f"x{j}_{t}")
        s.Add(sum(x[j, t] for t in range(T)) == f["energy_kwh"])
    grid = [s.NumVar(0, s.infinity(), f"g{t}") for t in range(T)]
    waste = [s.NumVar(0, s.infinity(), f"w{t}") for t in range(T)]
    pmax = s.NumVar(0, s.infinity(), "pmax")
    for t in range(T):
        flex_t = sum(x[j, t] for j in range(len(flex_loads)))
        s.Add(grid[t] >= base_kw[t] + flex_t - solar_kw[t])
        s.Add(waste[t] >= solar_kw[t] - base_kw[t] - flex_t)
        s.Add(pmax >= grid[t])
        if peak_cap_kw is not None:
            s.Add(grid[t] <= peak_cap_kw)
    s.Minimize(sum(tariff[t] * grid[t] + waste_lambda * waste[t] for t in range(T)) + peak_penalty * pmax)
    status = s.Solve()
    base_flex = [sum(f["baseline_kw"][t] for f in flex_loads) for t in range(T)]
    base_grid = _grid(base_kw, base_flex, solar_kw)
    base_cost = sum(tariff[t] * base_grid[t] for t in range(T))
    if status != pywraplp.Solver.OPTIMAL:
        return dict(status="infeasible", message="No schedule satisfies energy and capacity constraints "
                    "(check flexible-load windows, max power and any peak cap).",
                    baseline=dict(grid_kw=base_grid, cost=base_cost, peak_kw=max(base_grid)))
    opt_flex = [sum(x[j, t].solution_value() for j in range(len(flex_loads))) for t in range(T)]
    opt_grid = _grid(base_kw, opt_flex, solar_kw)
    opt_cost = sum(tariff[t] * opt_grid[t] for t in range(T))
    shifts = []
    for j, f in enumerate(flex_loads):
        new = [x[j, t].solution_value() for t in range(T)]
        moved = sum(max(0, new[t] - f["baseline_kw"][t]) for t in range(T))
        top = sorted(range(T), key=lambda t: new[t] - f["baseline_kw"][t], reverse=True)[:3]
        low = sorted(range(T), key=lambda t: new[t] - f["baseline_kw"][t])[:3]
        shifts.append(dict(load=f["name"], energy_kwh=f["energy_kwh"], moved_kwh=round(moved, 1),
                           baseline_kw=f["baseline_kw"], optimized_kw=new, essential=False,
                           move_to_hours=sorted(t for t in top if new[t] - f["baseline_kw"][t] > 1e-6),
                           move_from_hours=sorted(t for t in low if new[t] - f["baseline_kw"][t] < -1e-6),
                           reason=f"Shifted within the permitted window {f['window'][0]:02d}:00-{f['window'][1]:02d}:00 "
                                  f"toward lower-tariff / higher-solar hours; total energy unchanged."))
    return dict(status="optimal",
                baseline=dict(grid_kw=base_grid, cost=base_cost, peak_kw=max(base_grid), flex_kw=base_flex),
                optimized=dict(grid_kw=opt_grid, cost=opt_cost, peak_kw=max(opt_grid), flex_kw=opt_flex),
                cost_difference=base_cost - opt_cost, peak_reduction_kw=max(base_grid) - max(opt_grid),
                shifts=shifts, mode="recommendation",
                objective="min sum(tariff*grid + lambda*waste) + mu*Pmax")
