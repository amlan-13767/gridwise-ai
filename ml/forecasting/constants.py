"""Light-weight constants shared by training and serving (no heavy ML imports)."""
HORIZONS = {"1_hour": 1, "24_hours": 24, "7_days": 168}
SEED = 42
FEATURES = ["lag_a", "lag_b", "lag_c", "hour", "dow", "month", "is_weekend", "is_holiday",
            "temperature", "humidity", "occupancy", "zone_code", "bld_mean"]
ZONES = {"Academic": 0, "Hostel": 1, "Residential": 2}
