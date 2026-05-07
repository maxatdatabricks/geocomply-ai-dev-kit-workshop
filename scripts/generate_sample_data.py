"""
Generate synthetic fingerprint / geolocation event data for the
GeoComply x Databricks AI Dev Kit workshop.

Outputs (under <output_dir>, default ./data/):
  - fingerprint_events.parquet   bronze event stream
  - allowed_regions.csv          per-account geofence config
  - ip_watchlist.csv             bad-IP reputation list
  - ground_truth.csv             planted-anomaly labels (for validating risk scores)

Usage:
  python scripts/generate_sample_data.py
  python scripts/generate_sample_data.py --config scripts/sample_data_config.yaml
  python scripts/generate_sample_data.py --dry-run     # preview counts, no files written
  python scripts/generate_sample_data.py --format csv  # parquet (default) or csv

The script self-installs missing pip dependencies (pandas, numpy, pyyaml,
pyarrow) into the active interpreter so it runs cleanly on a fresh checkout.
"""

from __future__ import annotations

import argparse
import importlib
import random
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Dependency bootstrap — keeps the script self-sufficient on a fresh machine.
# ---------------------------------------------------------------------------
REQUIRED = {
    "pandas":  "pandas",
    "numpy":   "numpy",
    "yaml":    "pyyaml",
    "pyarrow": "pyarrow",   # parquet writer
}


def _ensure_deps() -> None:
    missing = []
    for mod, pkg in REQUIRED.items():
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[bootstrap] installing: {', '.join(missing)}", file=sys.stderr)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", *missing]
        )


_ensure_deps()

import numpy as np                     # noqa: E402
import pandas as pd                    # noqa: E402
import yaml                            # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def jitter_latlon(lat: float, lon: float, rng: random.Random, km: float = 25.0) -> tuple[float, float]:
    """Move a point by up to `km` in a random direction (city-scale jitter)."""
    deg = km / 111.0
    return lat + rng.uniform(-deg, deg), lon + rng.uniform(-deg, deg)


def random_ip(rng: random.Random, prefix: str | None = None) -> str:
    if prefix:
        rest = 4 - prefix.count(".")
        return prefix + ".".join(str(rng.randint(0, 255)) for _ in range(rest))
    return ".".join(str(rng.randint(1, 254)) for _ in range(4))


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
@dataclass
class GenContext:
    cfg: dict
    rng: random.Random
    np_rng: np.random.Generator
    start: datetime
    end: datetime
    baseline_end: datetime


def _build_accounts(ctx: GenContext) -> pd.DataFrame:
    cfg = ctx.cfg
    rng = ctx.rng
    homes = cfg["home_countries"]

    n_accounts = cfg["population"]["num_normal_accounts"]
    rows = []
    for i in range(n_accounts):
        home = rng.choice(homes)
        rows.append(
            {
                "account_id": f"acct_{i:06d}",
                "home_country": home["code"],
                "home_lat": home["lat"],
                "home_lon": home["lon"],
            }
        )
    return pd.DataFrame(rows)


def _build_devices(ctx: GenContext, accounts: pd.DataFrame) -> pd.DataFrame:
    """Each device has a primary account; some are shared across accounts (anomaly)."""
    cfg = ctx.cfg
    rng = ctx.rng
    n_devices = cfg["population"]["num_normal_devices"]
    rows = []
    for i in range(n_devices):
        acct = accounts.sample(1, random_state=rng.randint(0, 2**31)).iloc[0]
        rows.append(
            {
                "device_id": f"dev_{i:06d}",
                "primary_account_id": acct["account_id"],
                "home_country": acct["home_country"],
                "home_lat": acct["home_lat"],
                "home_lon": acct["home_lon"],
            }
        )
    return pd.DataFrame(rows)


def _allowed_regions(ctx: GenContext, accounts: pd.DataFrame) -> pd.DataFrame:
    """Per-account geofence: one row per (account, allowed_country)."""
    cfg = ctx.cfg
    rng = ctx.rng
    pct_multi = cfg["geofence"]["pct_accounts_with_multi_country_allowance"]
    all_codes = [c["code"] for c in cfg["home_countries"]]

    rows = []
    for _, a in accounts.iterrows():
        allowed = {a["home_country"]}
        if rng.random() < pct_multi:
            extras = rng.sample([c for c in all_codes if c != a["home_country"]],
                                k=rng.randint(1, 2))
            allowed.update(extras)
        for code in allowed:
            rows.append({"account_id": a["account_id"], "allowed_country": code})
    return pd.DataFrame(rows)


def _ip_watchlist(ctx: GenContext) -> pd.DataFrame:
    cfg = ctx.cfg["ip_watchlist"]
    rng = ctx.rng
    ips = []
    for _ in range(cfg["num_bad_ips"]):
        prefix = rng.choice(cfg["bad_ip_prefixes"])
        ips.append(random_ip(rng, prefix=prefix))
    return pd.DataFrame(
        {
            "ip_address": ips,
            "category": ["proxy_or_tor"] * len(ips),
            "added_at": [ctx.start.isoformat()] * len(ips),
        }
    )


def _normal_events(
    ctx: GenContext,
    devices: pd.DataFrame,
    accounts_idx: dict,
) -> list[dict]:
    cfg = ctx.cfg
    rng = ctx.rng
    lam = cfg["population"]["events_per_device_per_day"]
    duration_days = (ctx.end - ctx.start).days

    rows = []
    event_types = cfg["event_types"]
    channels = cfg["channels"]

    for _, dev in devices.iterrows():
        n_events = ctx.np_rng.poisson(lam * duration_days)
        for _ in range(n_events):
            ts = ctx.start + timedelta(seconds=rng.randint(0, duration_days * 86400))
            lat, lon = jitter_latlon(dev["home_lat"], dev["home_lon"], rng)
            rows.append(
                {
                    "event_id":        str(uuid.UUID(int=rng.getrandbits(128))),
                    "event_timestamp": ts,
                    "device_id":       dev["device_id"],
                    "account_id":      dev["primary_account_id"],
                    "ip_address":      random_ip(rng),
                    "country":         dev["home_country"],
                    "latitude":        round(lat, 5),
                    "longitude":       round(lon, 5),
                    "event_type":      rng.choice(event_types),
                    "channel":         rng.choice(channels),
                }
            )
    return rows


# ---- Anomaly planters -----------------------------------------------------

def _plant_impossible_travel(
    ctx: GenContext, devices: pd.DataFrame, gt: list[dict]
) -> list[dict]:
    cfg = ctx.cfg["anomalies"]["impossible_travel"]
    rng = ctx.rng
    foreign = ctx.cfg["foreign_countries"]
    rows = []
    chosen = devices.sample(cfg["num_devices"], random_state=rng.randint(0, 2**31))
    for _, dev in chosen.iterrows():
        # Pick a foreign country far from home.
        far = max(
            foreign,
            key=lambda c: haversine_km(dev["home_lat"], dev["home_lon"], c["lat"], c["lon"]),
        )
        t0 = ctx.start + timedelta(days=rng.randint(0, (ctx.end - ctx.start).days - 1))
        t1 = t0 + timedelta(minutes=rng.randint(5, cfg["max_minutes_between"]))
        for ts, country, lat, lon in [
            (t0, dev["home_country"], dev["home_lat"], dev["home_lon"]),
            (t1, far["code"],         far["lat"],     far["lon"]),
        ]:
            jlat, jlon = jitter_latlon(lat, lon, rng, km=10)
            rows.append(
                {
                    "event_id":        str(uuid.UUID(int=rng.getrandbits(128))),
                    "event_timestamp": ts,
                    "device_id":       dev["device_id"],
                    "account_id":      dev["primary_account_id"],
                    "ip_address":      random_ip(rng),
                    "country":         country,
                    "latitude":        round(jlat, 5),
                    "longitude":       round(jlon, 5),
                    "event_type":      "login",
                    "channel":         "web",
                }
            )
        gt.append({"entity_type": "device", "entity_id": dev["device_id"],
                   "anomaly": "impossible_travel"})
    return rows


def _plant_geofence_violations(
    ctx: GenContext, accounts: pd.DataFrame, devices: pd.DataFrame, gt: list[dict]
) -> list[dict]:
    cfg = ctx.cfg["anomalies"]["geofence_violation"]
    rng = ctx.rng
    foreign = ctx.cfg["foreign_countries"]
    duration_days = (ctx.end - ctx.start).days
    expected_events = ctx.cfg["population"]["events_per_device_per_day"] * duration_days

    # Only plant on accounts that already have a primary device. Keeps device
    # IDs in the standard dev_NNNNNN range and ensures foreign events mix with
    # the device s normal traffic so geofence_score lands in (0, 1) rather than
    # pinning to 1.0 on synthesized device-only-foreign rows.
    dev_by_acct = devices.groupby("primary_account_id")["device_id"].apply(list).to_dict()
    accts_with_device = accounts[accounts["account_id"].isin(dev_by_acct)]
    chosen = accts_with_device.sample(cfg["num_accounts"], random_state=rng.randint(0, 2**31))

    pct_min = cfg["min_pct_foreign_events"]
    pct_max = cfg["max_pct_foreign_events"]

    rows = []
    for _, a in chosen.iterrows():
        dev_id = dev_by_acct[a["account_id"]][0]
        pct = rng.uniform(pct_min, pct_max)
        n_foreign = max(3, int(expected_events * pct))
        for _ in range(n_foreign):
            country = rng.choice(foreign)
            ts = ctx.start + timedelta(seconds=rng.randint(0, duration_days * 86400))
            lat, lon = jitter_latlon(country["lat"], country["lon"], rng)
            rows.append(
                {
                    "event_id":        str(uuid.UUID(int=rng.getrandbits(128))),
                    "event_timestamp": ts,
                    "device_id":       dev_id,
                    "account_id":      a["account_id"],
                    "ip_address":      random_ip(rng),
                    "country":         country["code"],
                    "latitude":        round(lat, 5),
                    "longitude":       round(lon, 5),
                    "event_type":      rng.choice(ctx.cfg["event_types"]),
                    "channel":         rng.choice(ctx.cfg["channels"]),
                }
            )
        gt.append({"entity_type": "account", "entity_id": a["account_id"],
                   "anomaly": "geofence_violation"})
    return rows


def _plant_device_sharing(
    ctx: GenContext, accounts: pd.DataFrame, devices: pd.DataFrame, gt: list[dict]
) -> list[dict]:
    cfg = ctx.cfg["anomalies"]["device_sharing"]
    rng = ctx.rng
    chosen = devices.sample(cfg["num_devices"], random_state=rng.randint(0, 2**31))
    rows = []
    for _, dev in chosen.iterrows():
        sharers = accounts.sample(cfg["accounts_per_device"],
                                  random_state=rng.randint(0, 2**31))
        for _, acct in sharers.iterrows():
            for _ in range(rng.randint(3, 8)):
                ts = ctx.start + timedelta(seconds=rng.randint(0, (ctx.end - ctx.start).days * 86400))
                lat, lon = jitter_latlon(dev["home_lat"], dev["home_lon"], rng)
                rows.append(
                    {
                        "event_id":        str(uuid.UUID(int=rng.getrandbits(128))),
                        "event_timestamp": ts,
                        "device_id":       dev["device_id"],
                        "account_id":      acct["account_id"],
                        "ip_address":      random_ip(rng),
                        "country":         dev["home_country"],
                        "latitude":        round(lat, 5),
                        "longitude":       round(lon, 5),
                        "event_type":      rng.choice(ctx.cfg["event_types"]),
                        "channel":         rng.choice(ctx.cfg["channels"]),
                    }
                )
        gt.append({"entity_type": "device", "entity_id": dev["device_id"],
                   "anomaly": "device_sharing"})
    return rows


def _plant_behavioral_drift(
    ctx: GenContext, accounts: pd.DataFrame, devices: pd.DataFrame, gt: list[dict]
) -> list[dict]:
    cfg = ctx.cfg["anomalies"]["behavioral_drift"]
    rng = ctx.rng
    foreign = ctx.cfg["foreign_countries"]
    # Only plant on accounts that already have a primary device. Keeps device
    # IDs in the standard dev_NNNNNN range; no fabricated dev_extra_* rows.
    dev_by_acct = devices.groupby("primary_account_id")["device_id"].apply(list).to_dict()
    accts_with_device = accounts[accounts["account_id"].isin(dev_by_acct)]
    chosen = accts_with_device.sample(cfg["num_accounts"], random_state=rng.randint(0, 2**31))

    rows = []
    for _, a in chosen.iterrows():
        dev_id = dev_by_acct[a["account_id"]][0]

        # Baseline: 21 days, home country, business-hours (9-17 UTC)
        for _ in range(rng.randint(15, 25)):
            day = rng.randint(0, ctx.cfg["time_range"]["baseline_days"] - 1)
            hour = rng.randint(9, 17)
            ts = ctx.start + timedelta(days=day, hours=hour, minutes=rng.randint(0, 59))
            lat, lon = jitter_latlon(a["home_lat"], a["home_lon"], rng)
            rows.append(_drift_row(rng, ctx, ts, dev_id, a["account_id"],
                                   a["home_country"], lat, lon))

        # Drift period: last 9 days, foreign country, off-hours (1-5 UTC)
        new_country = rng.choice(foreign) if cfg["drift_country_shift"] else \
                      {"code": a["home_country"], "lat": a["home_lat"], "lon": a["home_lon"]}
        baseline_days = ctx.cfg["time_range"]["baseline_days"]
        total_days = (ctx.end - ctx.start).days
        for _ in range(rng.randint(8, 15)):
            day = rng.randint(baseline_days, total_days - 1)
            hour = (9 + cfg["drift_hour_shift_hours"]) % 24  # ~1-5 UTC if shift=8
            hour = (hour + rng.randint(-2, 2)) % 24
            ts = ctx.start + timedelta(days=day, hours=hour, minutes=rng.randint(0, 59))
            lat, lon = jitter_latlon(new_country["lat"], new_country["lon"], rng)
            rows.append(_drift_row(rng, ctx, ts, dev_id, a["account_id"],
                                   new_country["code"], lat, lon))

        gt.append({"entity_type": "account", "entity_id": a["account_id"],
                   "anomaly": "behavioral_drift"})
    return rows


def _drift_row(rng, ctx, ts, dev_id, acct_id, country, lat, lon) -> dict:
    return {
        "event_id":        str(uuid.UUID(int=rng.getrandbits(128))),
        "event_timestamp": ts,
        "device_id":       dev_id,
        "account_id":      acct_id,
        "ip_address":      random_ip(rng),
        "country":         country,
        "latitude":        round(lat, 5),
        "longitude":       round(lon, 5),
        "event_type":      rng.choice(ctx.cfg["event_types"]),
        "channel":         rng.choice(ctx.cfg["channels"]),
    }


def _plant_watchlist_hits(
    ctx: GenContext, devices: pd.DataFrame, watchlist: pd.DataFrame, gt: list[dict]
) -> list[dict]:
    cfg = ctx.cfg["anomalies"]["watchlist_hits"]
    rng = ctx.rng
    chosen = devices.sample(cfg["num_devices"], random_state=rng.randint(0, 2**31))
    bad_ips = watchlist["ip_address"].tolist()
    rows = []
    for _, dev in chosen.iterrows():
        for _ in range(rng.randint(8, 18)):
            use_bad = rng.random() < cfg["pct_events_from_bad_ip"]
            ip = rng.choice(bad_ips) if use_bad else random_ip(rng)
            ts = ctx.start + timedelta(seconds=rng.randint(0, (ctx.end - ctx.start).days * 86400))
            lat, lon = jitter_latlon(dev["home_lat"], dev["home_lon"], rng)
            rows.append(
                {
                    "event_id":        str(uuid.UUID(int=rng.getrandbits(128))),
                    "event_timestamp": ts,
                    "device_id":       dev["device_id"],
                    "account_id":      dev["primary_account_id"],
                    "ip_address":      ip,
                    "country":         dev["home_country"],
                    "latitude":        round(lat, 5),
                    "longitude":       round(lon, 5),
                    "event_type":      rng.choice(ctx.cfg["event_types"]),
                    "channel":         rng.choice(ctx.cfg["channels"]),
                }
            )
        gt.append({"entity_type": "device", "entity_id": dev["device_id"],
                   "anomaly": "watchlist_hits"})
    return rows


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------
def generate(cfg: dict) -> dict[str, pd.DataFrame]:
    rng = random.Random(cfg["seed"])
    np_rng = np.random.default_rng(cfg["seed"])
    start = parse_iso(cfg["time_range"]["start"]).astimezone(timezone.utc)
    end   = parse_iso(cfg["time_range"]["end"]).astimezone(timezone.utc)
    baseline_end = start + timedelta(days=cfg["time_range"]["baseline_days"])

    ctx = GenContext(cfg=cfg, rng=rng, np_rng=np_rng,
                     start=start, end=end, baseline_end=baseline_end)

    accounts  = _build_accounts(ctx)
    devices   = _build_devices(ctx, accounts)
    geofence  = _allowed_regions(ctx, accounts)
    watchlist = _ip_watchlist(ctx)

    gt: list[dict] = []
    accounts_idx = accounts.set_index("account_id").to_dict("index")

    rows: list[dict] = []
    rows.extend(_normal_events(ctx, devices, accounts_idx))
    rows.extend(_plant_impossible_travel(ctx, devices, gt))
    rows.extend(_plant_geofence_violations(ctx, accounts, devices, gt))
    rows.extend(_plant_device_sharing(ctx, accounts, devices, gt))
    rows.extend(_plant_behavioral_drift(ctx, accounts, devices, gt))
    rows.extend(_plant_watchlist_hits(ctx, devices, watchlist, gt))

    events = pd.DataFrame(rows).sort_values("event_timestamp").reset_index(drop=True)
    events["event_timestamp"] = pd.to_datetime(events["event_timestamp"], utc=True)

    return {
        "events": events,
        "allowed_regions": geofence,
        "ip_watchlist": watchlist,
        "ground_truth": pd.DataFrame(gt),
    }


def write_outputs(tables: dict[str, pd.DataFrame], out_dir: Path, fmt: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    name_map = {
        "events":          "fingerprint_events",
        "allowed_regions": "allowed_regions",
        "ip_watchlist":    "ip_watchlist",
        "ground_truth":    "ground_truth",
    }
    for key, df in tables.items():
        base = out_dir / name_map[key]
        if key == "events" and fmt == "parquet":
            path = base.with_suffix(".parquet")
            # us precision so Spark/Photon can read it (rejects pyarrow's default ns timestamps).
            df.to_parquet(path, index=False, coerce_timestamps="us", allow_truncated_timestamps=True)
        else:
            path = base.with_suffix(".csv")
            df.to_csv(path, index=False)
        print(f"  wrote {path}  ({len(df):,} rows)")


def summarise(tables: dict[str, pd.DataFrame]) -> None:
    e = tables["events"]
    print("\n=== summary ===")
    print(f"events:           {len(e):,}")
    print(f"distinct devices: {e['device_id'].nunique():,}")
    print(f"distinct accounts:{e['account_id'].nunique():,}")
    print(f"date range:       {e['event_timestamp'].min()} -> {e['event_timestamp'].max()}")
    print(f"countries:        {sorted(e['country'].unique())}")
    print(f"allowed_regions:  {len(tables['allowed_regions']):,}")
    print(f"ip_watchlist:     {len(tables['ip_watchlist']):,}")
    print(f"ground_truth:     {len(tables['ground_truth']):,}")
    print(tables["ground_truth"]["anomaly"].value_counts().to_string())


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default=str(repo_root / "scripts" / "sample_data_config.yaml"))
    p.add_argument("--output-dir", default=None,
                   help="Override output_dir from config")
    p.add_argument("--format", choices=["parquet", "csv"], default="parquet",
                   help="Format for the events table (default parquet)")
    p.add_argument("--dry-run", action="store_true",
                   help="Generate in memory and print summary; do not write files")
    args = p.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    out_dir = Path(args.output_dir or cfg.get("output_dir", "data"))
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir

    print(f"[generate_sample_data] config: {args.config}")
    print(f"[generate_sample_data] output: {out_dir}  (dry-run={args.dry_run})")

    tables = generate(cfg)
    summarise(tables)

    if args.dry_run:
        print("\n[dry-run] no files written.")
    else:
        print(f"\nwriting outputs to {out_dir}/")
        write_outputs(tables, out_dir, args.format)

    return 0


if __name__ == "__main__":
    sys.exit(main())
