"""SIMULATED sample campus definition. NOT the real NIT Rourkela inventory.
Coordinates are approximate demo positions around a placeholder campus centre."""
import numpy as np

CENTER = (22.2536, 84.9006)  # approximate demo centre, not surveyed


def build_campus(seed: int = 42):
    rng = np.random.default_rng(seed)
    b = []

    def add(code, name, zone, btype, area, cap, base_kw, hvac_share, i, n):
        ang = 2 * np.pi * i / max(n, 1)
        r = {"Academic": 0.0025, "Hostel": 0.0055, "Residential": 0.0085}[zone]
        b.append(dict(
            building_id=code, building_name=name, zone_type=zone, building_type=btype,
            floor_area=area, capacity=cap, base_kw=base_kw, hvac_share=hvac_share,
            lat=round(CENTER[0] + r * np.sin(ang) + rng.normal(0, .0004), 6),
            lon=round(CENTER[1] + r * np.cos(ang) + rng.normal(0, .0004), 6)))

    acad = [("Academic Block A", "lecture"), ("Academic Block B", "lecture"),
            ("Computer Science Department", "computer_lab"), ("Central Library", "library"),
            ("Electrical Dept", "research_lab"), ("Mechanical Dept", "research_lab"),
            ("Administration Building", "admin"), ("Chemistry Labs", "research_lab"),
            ("Lecture Hall Complex", "lecture"), ("Data Centre Annex", "server_room")]
    for i, (n, t) in enumerate(acad):
        add(f"ACD-{i+1:02d}", n, "Academic", t, int(rng.integers(2500, 7000)),
            int(rng.integers(300, 1200)), float(rng.uniform(25, 70)),
            0.25 if t != "server_room" else 0.4, i, len(acad))
    for i in range(20):
        cap = int(rng.integers(300, 800))
        add(f"HST-{i+1:02d}", f"Hostel {chr(65+i)}", "Hostel", "hostel",
            int(rng.integers(4000, 9000)), cap, float(cap * rng.uniform(.045, .07)), 0.12, i, 20)
    for i in range(5):
        add(f"RES-{i+1:02d}", f"Residential Cluster {i+1}", "Residential", "residential",
            int(rng.integers(6000, 12000)), int(rng.integers(60, 140)),
            float(rng.uniform(40, 80)), 0.2, i, 5)
    return b
