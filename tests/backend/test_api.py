import datetime as dt
from backend.app.iot.ingest import device_key


def test_login_logout_me(client, admin):
    assert client.get("/api/auth/me", headers=admin).json()["role"] == "super_admin"
    assert client.post("/api/auth/logout", headers=admin).status_code == 200
    assert client.post("/api/auth/login", json={"email": "admin@gridwise.demo", "password": "wrong-password"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_registration_admin_only_no_public_signup(client, admin, manager):
    body = dict(name="New Person", email="new.user@example.org", password="LongEnoughPass1!", role="viewer")
    assert client.post("/api/auth/register", json=body).status_code == 401
    assert client.post("/api/auth/register", json=body, headers=manager).status_code == 403
    assert client.post("/api/auth/register", json=body, headers=admin).status_code == 201
    assert client.post("/api/auth/register", json=body, headers=admin).status_code == 409
    assert client.post("/api/auth/register", json=dict(body, email="x@example.org", password="short"), headers=admin).status_code == 422


def test_role_authorization(client, viewer, manager, zonemgr):
    assert client.patch("/api/settings", json={"electricity_tariff": 7}, headers=manager).status_code == 403
    assert client.post("/api/zones", json={"name": "Z", "zone_type": "Academic"}, headers=viewer).status_code == 403
    assert client.get("/api/users", headers=viewer).status_code == 403
    assert client.post("/api/forecast/run", headers=viewer).status_code == 403


def test_zone_manager_scope(client, zonemgr):
    zones = client.get("/api/zones", headers=zonemgr).json()
    assert [z["zone_type"] for z in zones] == ["Hostel"]
    assert client.get("/api/energy/zone-dashboard/academic", headers=zonemgr).status_code == 403
    assert client.get("/api/energy/zone-dashboard/hostel", headers=zonemgr).status_code == 200
    items = client.get("/api/buildings?limit=200", headers=zonemgr).json()["items"]
    assert items and all(b["zone_type"] == "Hostel" for b in items)


def test_residential_privacy_for_viewer(client, viewer, admin):
    items = client.get("/api/buildings?limit=200", headers=viewer).json()["items"]
    assert all(b["zone_type"] != "Residential" for b in items)
    d = client.get("/api/energy/zone-dashboard/residential", headers=viewer).json()
    assert d["restricted"] and "by_building" not in d
    assert client.get("/api/energy/consumption?group=building&zone=Residential", headers=viewer).json()["items"] == []
    full = client.get("/api/energy/zone-dashboard/residential", headers=admin).json()
    assert "by_building" in full


def test_zone_building_meter_creation(client, admin):
    zid = client.get("/api/zones", headers=admin).json()[0]["id"]
    r = client.post("/api/zones", json={"name": "Test Zone", "zone_type": "Academic"}, headers=admin); assert r.status_code == 201
    assert client.post("/api/zones", json={"name": "Test Zone", "zone_type": "Academic"}, headers=admin).status_code == 409
    b = client.post("/api/buildings", json=dict(zone_id=zid, code="TST-01", building_name="Test Block", building_type="lecture", floor_area=1000, capacity=100), headers=admin)
    assert b.status_code == 201 and b.json()["data_source"] == "real"
    assert client.post("/api/buildings", json=dict(zone_id=zid, code="TST-01", building_name="Dup", building_type="x"), headers=admin).status_code == 409
    assert client.post("/api/buildings", json=dict(zone_id=zid, code="TST-02", building_name="Bad", building_type="x", floor_area=-5), headers=admin).status_code == 422
    bid = b.json()["id"]
    assert client.patch(f"/api/buildings/{bid}", json={"capacity": 250}, headers=admin).json()["capacity"] == 250
    m = client.post("/api/meters", json=dict(building_id=bid, meter_identifier="MTR-TST-01", data_source="real"), headers=admin)
    assert m.status_code == 201
    assert client.post("/api/meters", json=dict(building_id=bid, meter_identifier="MTR-TST-01"), headers=admin).status_code == 409
    assert client.get(f"/api/buildings/{bid}", headers=admin).json()["meters"][0]["data_source"] == "real"


def _payload(meter, ts, kw=25.0, **k):
    return dict(meter_id=meter, timestamp=ts.strftime("%Y-%m-%dT%H:%M:%SZ"), power_kw=kw, energy_kwh=kw / 4, voltage=230, current=10, source="simulated", **k)


def test_ingestion_pipeline(client):
    ts = dt.datetime.now(dt.timezone.utc).replace(second=37, microsecond=0)  # off the 15-min seed grid
    key = {"X-Device-Key": device_key("test-secret-key", "MTR-ACD-01")}
    p = _payload("MTR-ACD-01", ts)
    r = client.post("/api/iot/ingest", json=p, headers=key); assert r.status_code == 201 and r.json()["status"] == "stored"
    r = client.post("/api/iot/ingest", json=p, headers=key); assert r.json()["status"] == "duplicate"           # duplicate handling
    assert client.post("/api/iot/ingest", json=p, headers={"X-Device-Key": "bad"}).status_code == 401           # unauthorised device
    assert client.post("/api/iot/ingest", json=p).status_code == 401
    bad = {k: v for k, v in p.items() if k != "power_kw"}                                                      # missing data
    assert client.post("/api/iot/ingest", json=bad, headers=key).status_code == 422
    assert client.post("/api/iot/ingest", json=dict(p, meter_id="NOPE"), headers=key).status_code == 422
    fut = _payload("MTR-ACD-01", ts + dt.timedelta(hours=3))
    assert client.post("/api/iot/ingest", json=fut, headers=key).status_code == 422
    old = _payload("MTR-ACD-01", ts - dt.timedelta(hours=5), 30)
    assert client.post("/api/iot/ingest", json=old, headers=key).json()["quality"] == "delayed"                # delayed message
    wrong = dict(_payload("MTR-ACD-01", ts + dt.timedelta(minutes=1)), source="real")
    assert client.post("/api/iot/ingest", json=wrong, headers=key).status_code == 422                          # source label mismatch
    sus = _payload("MTR-ACD-01", ts + dt.timedelta(minutes=2), kw=99999)
    assert client.post("/api/iot/ingest", json=sus, headers=key).json()["quality"] == "suspect"


def test_device_disconnection_detection(client, admin):
    from backend.app.iot.ingest import device_status
    from backend.app.models.tables import Meter
    now = dt.datetime(2026, 1, 1, 12)
    m = Meter(meter_identifier="x", building_id=1, status="active", last_seen=now - dt.timedelta(minutes=5))
    assert device_status(m, now) == "online"
    m.last_seen = now - dt.timedelta(hours=2); assert device_status(m, now) == "stale"
    m.last_seen = now - dt.timedelta(days=2); assert device_status(m, now) == "offline"
    m.last_seen = None; assert device_status(m, now) == "never_seen"
    items = client.get("/api/iot/devices", headers=admin).json()["items"]
    assert all(i["data_source"] in ("simulated", "real") for i in items)


def test_dashboard_aggregation_consistency(client, admin):
    ov = client.get("/api/energy/overview?days=30", headers=admin).json()
    daily = client.get("/api/energy/consumption?granularity=day&days=30", headers=admin).json()["items"]
    assert abs(sum(d["kwh"] for d in daily) - ov["total_kwh"]) / ov["total_kwh"] < 1e-3
    zones = client.get("/api/energy/zones?days=30", headers=admin).json()["items"]
    assert abs(sum(z["kwh"] for z in zones) - ov["total_kwh"]) / ov["total_kwh"] < 1e-3
    assert ov["data_mode"] == "SIMULATED DEMONSTRATION DATA"
    assert ov["peak"]["kw"] > ov["current_kw"] * 0.5
    one = client.get("/api/energy/consumption?granularity=hour&days=2&zone=Hostel", headers=admin).json()["items"]
    assert 40 <= len(one) <= 50


def test_filters(client, admin):
    b = client.get("/api/energy/buildings?zone=Academic", headers=admin).json()["items"]
    assert all(i["zone"] == "Academic" for i in b) and len(b) == 10
    assert client.get("/api/energy/consumption?source=real", headers=admin).json()["items"] == []


def test_forecast_output_schema(client, admin):
    for h in ("1_hour", "24_hours", "7_days"):
        f = client.get(f"/api/forecast?scope=campus&horizon={h}", headers=admin).json()
        assert f["forecast"] and set(f["forecast"][0]) == {"ts", "kw", "lower", "upper"}
        assert all(p["lower"] <= p["kw"] <= p["upper"] and p["kw"] >= 0 for p in f["forecast"])
    assert len(client.get("/api/forecast?scope=campus&horizon=24_hours", headers=admin).json()["forecast"]) == 24
    assert len(client.get("/api/forecast?scope=campus&horizon=7_days", headers=admin).json()["forecast"]) == 168
    assert client.get("/api/forecast/3", headers=admin).status_code == 200
    ev = client.get("/api/forecast/evaluation", headers=admin).json()
    assert "baseline_hourly_average" in ev["horizons"]["24_hours"]


def test_anomalies_and_review(client, admin, viewer, manager):
    a = client.get("/api/anomalies?status=open&limit=5", headers=admin).json()["items"][0]
    for k in ("building_id", "timestamp", "observed_kw", "expected_kw", "deviation_pct", "severity", "detection_method", "baseline"):
        assert k in a
    assert "not confirmed wastage" in a["disclaimer"]
    assert client.patch(f"/api/anomalies/{a['id']}/review", json={"status": "investigating"}, headers=viewer).status_code == 403
    r = client.patch(f"/api/anomalies/{a['id']}/review", json={"status": "investigating", "note": "checking"}, headers=manager)
    assert r.status_code == 200 and client.get(f"/api/anomalies/{a['id']}", headers=admin).json()["status"] == "investigating"
    assert client.patch(f"/api/anomalies/{a['id']}/review", json={"status": "bogus"}, headers=manager).status_code == 422


def test_cooling(client, admin, zonemgr):
    an = client.get("/api/cooling/analysis", headers=admin).json()["items"]
    flagged = [x for x in an if x["schedule_flag"]]
    assert flagged and "ESTIMATE" in flagged[0]["assumptions"]
    r = client.post("/api/cooling/optimize", json={"building_id": flagged[0]["building_id"]}, headers=admin).json()
    assert r["status"] == "optimal" and r["energy_saving_kwh"] > 0 and r["approval_required"]
    assert all(f >= 0.25 - 1e-9 for f in r["fractions"])
    assert all(r["fractions"][h] == 1.0 for h in range(24) if r["occupied"][h])   # comfort constraint
    other = next(x for x in an if x["zone"] == "Academic")
    assert client.post("/api/cooling/optimize", json={"building_id": other["building_id"]}, headers=zonemgr).status_code == 403


def test_renewable(client, admin):
    o = client.get("/api/renewable/overview", headers=admin).json()
    assert o["data_mode"].startswith("SIMULATED") and all(a["data_source"] == "simulated" for a in o["assets"])
    assert o["wind"]["installed"] is False and o["battery"]["available"] is False
    f = client.get("/api/renewable/forecast", headers=admin).json()
    assert len(f["items"]) == 24 and all(i["solar_kw"] >= 0 for i in f["items"])
    night = [i for i in f["items"] if i["solar_kw"] < 1]
    assert len(night) >= 8


def test_optimization_flow(client, admin, manager, viewer):
    r = client.post("/api/optimization/run", json={"peak_penalty": 2}, headers=manager).json()
    assert r["mode"] == "recommendation" and r["status"] == "pending_review"
    assert r["summary"]["optimized_cost"] <= r["summary"]["baseline_cost"] + 1e-6
    assert client.post(f"/api/optimization/{r['id']}/approve", headers=viewer).status_code == 403
    assert client.post(f"/api/optimization/{r['id']}/approve", headers=manager).json()["status"] == "approved"
    assert client.post(f"/api/optimization/{r['id']}/approve", headers=manager).status_code == 409
    inf = client.post("/api/optimization/run", json={"peak_cap_kw": 100}, headers=manager).json()
    assert inf["status"] == "infeasible"   # infeasible scenario handled gracefully
    assert client.post(f"/api/optimization/{inf['id']}/approve", headers=manager).status_code == 409


def test_recommendation_lifecycle(client, manager, viewer, zonemgr):
    items = client.get("/api/recommendations?limit=200", headers=manager).json()["items"]
    r = next(i for i in items if i["status"] == "pending" and i["type"] == "rule_based_alert")
    assert r["saving_label"].startswith("ESTIMATED")
    assert client.patch(f"/api/recommendations/{r['id']}", json={"status": "implemented"}, headers=manager).status_code == 409  # must approve first
    assert client.patch(f"/api/recommendations/{r['id']}", json={"status": "approved"}, headers=viewer).status_code == 403
    assert client.post(f"/api/recommendations/{r['id']}/review", json={"decision": "approve"}, headers=manager).json()["status"] == "approved"
    assert client.patch(f"/api/recommendations/{r['id']}", json={"measured_saving_kwh": 5}, headers=manager).status_code == 409
    d = client.patch(f"/api/recommendations/{r['id']}", json={"status": "implemented"}, headers=manager).json()
    assert d["type"] == "verified_action" and d["implemented_at"]
    d = client.patch(f"/api/recommendations/{r['id']}", json={"measured_saving_kwh": 12.5}, headers=manager).json()
    assert d["type"] == "measured_saving" and d["saving_label"] == "MEASURED"
    zr = next(i for i in client.get("/api/recommendations?limit=200", headers=zonemgr).json()["items"] if i["status"] == "pending")
    assert client.post(f"/api/recommendations/{zr['id']}/review", json={"decision": "approve"}, headers=zonemgr).status_code == 403
    assert client.post(f"/api/recommendations/{zr['id']}/review", json={"decision": "investigate", "note": "on it"}, headers=zonemgr).status_code == 200


def test_reports_and_csv(client, admin, viewer):
    r = client.get("/api/reports/energy?format=csv&days=7", headers=admin)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.splitlines()
    assert lines[0].startswith("# GRIDWISE AI") and "SIMULATED" in lines[0] and "kwh" in lines[1]
    assert client.get("/api/reports/buildings?format=csv", headers=viewer).status_code == 200
    s = client.get("/api/reports/sustainability", headers=admin).json()
    ef = s["emissions_factor_kg_per_kwh"]
    assert abs(s["estimated_emissions_kg"] - (s["total_kwh"] - s["renewable_kwh"]) * ef) < 1e-3
    assert "ESTIMATE" in s["renewable_note"]
    assert client.get("/api/reports/models", headers=viewer).json()["rows"]


def test_settings_validation_and_effect(client, admin):
    assert client.patch("/api/settings", json={"grid_emissions_factor": -1}, headers=admin).status_code == 422
    assert client.patch("/api/settings", json={"nonsense": 1}, headers=admin).status_code == 422
    base = client.get("/api/reports/sustainability", headers=admin).json()["estimated_emissions_kg"]
    assert client.patch("/api/settings", json={"grid_emissions_factor": 0.41}, headers=admin).status_code == 200
    new = client.get("/api/reports/sustainability", headers=admin).json()["estimated_emissions_kg"]
    assert abs(new / base - 0.41 / 0.82) < 1e-6
    client.patch("/api/settings", json={"grid_emissions_factor": 0.82}, headers=admin)


def test_data_source_labelling(client, admin):
    ms = client.get("/api/meters", headers=admin).json()
    assert all(m["data_source"] in ("simulated", "real") for m in ms)
    rd = client.get("/api/meters/1/readings?limit=3", headers=admin).json()
    assert rd["data_source"] == "simulated" and all(r["data_source"] == "simulated" for r in rd["items"])


def test_model_governance(client, admin, manager):
    ms = client.get("/api/models", headers=admin).json()["items"]
    assert all(m["status"] == "pending_review" for m in ms)   # nothing auto-promoted
    assert client.post(f"/api/models/{ms[0]['id']}/review", json={"decision": "promote"}, headers=manager).status_code == 403
    assert client.post(f"/api/models/{ms[0]['id']}/review", json={"decision": "promote"}, headers=admin).json()["status"] == "production"


def test_audit_log(client, admin):
    acts = {a["action"] for a in client.get("/api/audit-logs?limit=300", headers=admin).json()["items"]}
    assert {"login", "login_failed", "user_created"} <= acts


def test_health_and_cors(client):
    h = client.get("/api/health").json()
    assert h["mode"] == "monitoring_and_recommendation_only" and h["database"] == "ok"
    assert h["simulated_data_loaded"] is True and h["first_admin_configured"] is True
    assert not any(k in h for k in ("database_url", "secret", "email"))
    r = client.options("/api/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers


def test_renewable_attributed_to_filtered_scope(client, admin):
    camp = client.get("/api/energy/overview?days=30", headers=admin).json()
    res = client.get("/api/energy/overview?days=30&zone=Residential", headers=admin).json()
    acad = client.get("/api/energy/overview?days=30&zone=Academic", headers=admin).json()
    assert res["renewable_kwh"] == 0 and res["renewable_pct"] == 0          # solar assets are academic only
    assert abs(acad["renewable_kwh"] - camp["renewable_kwh"]) < 1e-6


def test_response_cache_is_per_user_validated_and_invalidated_on_writes(client, admin, manager, viewer):
    p = "/api/energy/zones?days=30"
    a1 = client.get(p, headers=admin); a2 = client.get(p, headers=admin)
    assert a1.status_code == 200 and a2.headers.get("x-cache") == "HIT" and a1.json() == a2.json()
    assert client.get(p).status_code == 401                                       # no token: never served from cache
    assert client.get(p, headers={"Authorization": "Bearer junk.token.here"}).status_code == 401
    v = client.get("/api/energy/consumption?group=building&zone=Residential", headers=viewer).json()["items"]
    assert v == []                                                                # viewer privacy rule still applies
    assert client.get("/api/energy/consumption?group=building&zone=Residential", headers=admin).json()["items"] != []  # not shared across users
    client.patch("/api/settings", json={"electricity_tariff": 6.0}, headers=admin)  # a write clears the cache
    assert client.get(p, headers=admin).headers.get("x-cache") == "MISS"


def test_cached_csv_keeps_headers(client, admin):
    for _ in range(2):
        r = client.get("/api/reports/energy?format=csv&days=7", headers=admin)
        assert r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"]
    assert r.headers.get("x-cache") == "HIT"
