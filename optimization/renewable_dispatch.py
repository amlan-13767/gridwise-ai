"""Simple renewable surplus/deficit accounting against forecast demand."""
def dispatch(demand_kw, solar_kw):
    out = []
    for d, s in zip(demand_kw, solar_kw):
        used = min(d, s)
        out.append(dict(solar_used_kw=used, surplus_kw=max(0.0, s - d), deficit_kw=max(0.0, d - s),
                        renewable_share=(used / d if d > 0 else 0.0)))
    return out
