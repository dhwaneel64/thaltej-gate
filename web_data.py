"""Data for the web app: the schedule it simulates, and a live-delay snapshot.

  python web_data.py --schedule            # schedule JSON (baked into the page)
  python web_data.py --live --hours 3      # live delays for trains due in the next N hours
                                           # -> paste into the app's Sync sheet
  python web_data.py --build               # gate_template.html + schedule -> gate.html
  python web_data.py --site                # site_template.html + schedule -> site/index.html

The JSON modes print to stdout.
"""
import argparse
import datetime as dt
import json

import pandas as pd

import crossing_sim as cs


def schedule_json(path="trains.csv"):
    df, pool, _ = cs.load(path)
    trains = []
    for r in df.itertuples():
        days = sum(1 << i for i, d in enumerate(cs.DAYS) if d in r.crossing_days)
        trains.append(dict(
            no=r.train_no,
            nm=r.name,          # left as-is: these read as station-board names
            dir=r.direction,
            halt=int(r.halts_ABD),
            cm=int(r.crossing_min),
            days=days,
            avg=(None if pd.isna(r.avg_delay_min) else round(float(r.avg_delay_min), 1)),
        ))
    trains.sort(key=lambda t: t["cm"])
    return dict(
        generated=dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        params=cs.DEFAULTS,
        live_sd=dict(base=cs.LIVE_SD_BASE, frac=cs.LIVE_SD_FRAC, age=cs.LIVE_SD_AGE),
        live_max_age_min=cs.LIVE_MAX_AGE_MIN,
        pool=[round(float(v), 1) for v in sorted(pool)],
        trains=trains,
    )


def live_json(hours=3.0, path="trains.csv", pause=cs.LIVE_PAUSE, timeout=cs.LIVE_TIMEOUT):
    """Live delays for every train due at the crossing within the next `hours`."""
    _, _, by_day = cs.load(path)
    now = dt.datetime.now()
    weekday = cs.DAYS[now.weekday()]
    at = f"{now.hour:02d}:{now.minute:02d}"
    window = cs.nearby_trains(by_day, weekday, at, before=15, after=int(hours * 60))
    nos = list(dict.fromkeys(window["train_no"]))
    live = cs.fetch_live(nos, pause=pause, timeout=timeout, verbose=False)
    return dict(
        fetched_at=now.astimezone().isoformat(timespec="seconds"),
        horizon_hours=hours,
        delays={no: dict(delay=r["delay_min"], at=r.get("at"), age=r.get("age_min"),
                         run_date=r.get("run_date"), source=r["source"], note=r["note"])
                for no, r in live.items()},
    )


def build(template="gate_template.html", out="gate.html", path="trains.csv"):
    """Splice the schedule into the page template."""
    html = open(template, encoding="utf-8").read()
    marker = "/*__SCHEDULE__*/"
    assert marker in html, f"{template} has no {marker} placeholder"
    html = html.replace(marker, json.dumps(schedule_json(path), separators=(",", ":")))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    return out, len(html)


def build_site(template="site_template.html", out="site/index.html", path="trains.csv"):
    """Splice the schedule into the standalone website."""
    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)
    html = open(template, encoding="utf-8").read()
    marker = "/*__SCHEDULE__*/"
    assert marker in html, f"{template} has no {marker} placeholder"
    html = html.replace(marker, json.dumps(schedule_json(path), separators=(",", ":")))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    return out, len(html)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trains", default="trains.csv")
    ap.add_argument("--schedule", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--hours", type=float, default=3.0)
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--site", action="store_true")
    a = ap.parse_args()
    if a.site:
        out, n = build_site(path=a.trains)
        print(f"wrote {out} ({n:,} bytes)")
    elif a.build:
        out, n = build(path=a.trains)
        print(f"wrote {out} ({n:,} bytes)")
    elif a.schedule:
        print(json.dumps(schedule_json(a.trains), separators=(",", ":")))
    elif a.live:
        print(json.dumps(live_json(a.hours, a.trains), indent=1))
    else:
        ap.print_help()
