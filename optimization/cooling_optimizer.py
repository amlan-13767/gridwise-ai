"""Cooling schedule LP (SciPy linprog). Decision x_t in [lo_t, 1] = fraction of the building's
required cooling load served at hour t. Occupied hours must be served fully (comfort);
unoccupied hours may be set back to `setback_min` (equipment / safety floor).
Minimise sum tariff_t * load_t * x_t. Recommendation only; never actuates HVAC."""
import numpy as np
from scipy.optimize import linprog


def optimize_cooling(required_kw, occupied, tariff, setback_min=0.25, critical=False):
    """required_kw: 24 values (cooling load if fully served). occupied: 24 bools. critical: server room."""
    T = len(required_kw)
    c = np.array([tariff[t] * required_kw[t] for t in range(T)], float)
    lo = np.array([1.0 if (occupied[t] or critical) else setback_min for t in range(T)])
    res = linprog(c, bounds=[(lo[t], 1.0) for t in range(T)], method="highs")
    if not res.success:
        return dict(status="infeasible", message=res.message)
    x = res.x
    opt = [float(required_kw[t] * x[t]) for t in range(T)]
    return dict(status="optimal", optimized_kw=opt, fractions=[float(v) for v in x],
                energy_saving_kwh=float(sum(required_kw) - sum(opt)),
                cost_saving=float(sum(tariff[t] * (required_kw[t] - opt[t]) for t in range(T))),
                constraints=dict(setback_min=setback_min, occupied_hours_fully_served=True, critical_load=critical),
                mode="recommendation")


def rule_based_schedule_check(cooling_kw, occupancy, capacity, local_hours, threshold=0.05):
    """Return indices where cooling runs while occupancy is below threshold*capacity."""
    return [i for i, (c, o, h) in enumerate(zip(cooling_kw, occupancy, local_hours))
            if c > 0.5 and o < threshold * capacity]
