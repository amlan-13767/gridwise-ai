import numpy as np
from optimization.load_scheduling import optimize_load_shifting
from optimization.cooling_optimizer import optimize_cooling, rule_based_schedule_check
from optimization.renewable_dispatch import dispatch

T = 24
tariff = [6.0] * 18 + [8.5] * 4 + [6.0] * 2
solar = [0] * 7 + [50, 120, 200, 260, 300, 300, 260, 200, 120, 50] + [0] * 7
base = [300 + 100 * np.exp(-((h - 19) / 3) ** 2) for h in range(T)]


def loads(window=(5, 19)):
    b = [0.0] * T; b[17] = 50.0; b[18] = 50.0
    return [dict(name="pump", baseline_kw=b, energy_kwh=100.0, window=window, max_kw=60.0, essential=False)]


def test_constraints_energy_conserved_and_capacity():
    r = optimize_load_shifting(base, solar, tariff, loads())
    assert r["status"] == "optimal"
    s = r["shifts"][0]
    assert abs(sum(s["optimized_kw"]) - 100.0) < 1e-6                           # energy conservation
    assert max(s["optimized_kw"]) <= 60.0 + 1e-9                                  # equipment limit
    assert all(v < 1e-9 for h, v in enumerate(s["optimized_kw"]) if not 5 <= h < 19)  # window respected


def test_energy_balance_grid_covers_demand_minus_solar():
    r = optimize_load_shifting(base, solar, tariff, loads())
    for t in range(T):
        need = base[t] + r["optimized"]["flex_kw"][t] - solar[t]
        assert abs(r["optimized"]["grid_kw"][t] - max(0, need)) < 1e-6


def test_optimized_not_worse_than_baseline_and_shifts_off_peak():
    r = optimize_load_shifting(base, solar, tariff, loads())
    assert r["optimized"]["cost"] <= r["baseline"]["cost"] + 1e-6 and r["cost_difference"] > 0
    assert r["optimized"]["flex_kw"][18] < r["baseline"]["flex_kw"][18]          # moved out of 18:00 peak tariff


def test_infeasible_handled():
    r = optimize_load_shifting(base, solar, tariff, loads(window=(17, 18)))       # 100 kWh in 1 h with 60 kW cap
    assert r["status"] == "infeasible" and "message" in r
    r2 = optimize_load_shifting(base, solar, tariff, loads(), peak_cap_kw=10)
    assert r2["status"] == "infeasible"


def test_essential_loads_not_shifted():
    r = optimize_load_shifting(base, solar, tariff, [])
    assert r["status"] == "optimal" and r["baseline"]["grid_kw"] == r["optimized"]["grid_kw"]
    assert all(not s["essential"] for s in optimize_load_shifting(base, solar, tariff, loads())["shifts"])


def test_cooling_constraints():
    req = [10.0] * 24; occ = [8 <= h < 18 for h in range(24)]
    r = optimize_cooling(req, occ, tariff, setback_min=0.25)
    assert r["status"] == "optimal"
    for h in range(24):
        assert r["fractions"][h] >= 0.25 - 1e-9
        if occ[h]:
            assert abs(r["fractions"][h] - 1.0) < 1e-9
    assert r["energy_saving_kwh"] > 0 and r["mode"] == "recommendation"
    crit = optimize_cooling(req, occ, tariff, critical=True)
    assert crit["energy_saving_kwh"] == 0                                         # server rooms keep full cooling


def test_rule_based_schedule_check():
    idx = rule_based_schedule_check([5, 5, 0], [0, 50, 0], 100, [19, 12, 3])
    assert idx == [0]


def test_renewable_dispatch_balance():
    out = dispatch([100, 50], [40, 80])
    assert out[0]["deficit_kw"] == 60 and out[1]["surplus_kw"] == 30
    assert all(abs(o["solar_used_kw"] + o["surplus_kw"] - s) < 1e-9 for o, s in zip(out, [40, 80]))
