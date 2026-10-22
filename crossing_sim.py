"""
Monte Carlo model of the Thaltej level crossing (near Ambli Road, Ahmedabad).

For a chosen weekday, each simulated replay of that day:
  1. Takes the trains scheduled to reach the crossing that weekday (plus the
     previous and next day, so late-night spillover across midnight is handled).
  2. Shifts each train by a random delay (gamma-distributed around its average delay).
  3. Adds freight trains at random times (Poisson count, night-weighted).
  4. Turns each train into a closure: gate drops (L - 1) min before the train reaches
     the crossing and lifts 1 min after.
  5. Merges closures that overlap or are less than `merge_gap` minutes apart
     (gateman keeps the gate down if the next train is close).
  6. For every arrival minute: closed or not, and minutes until it opens.

--live does the same for *today*, but first looks up how late the trains due
around your arrival are running right now, and uses those delays instead of
their historical averages, with a much tighter spread (see LIVE_SD_BASE).

Usage:
  python crossing_sim.py --day Thu --arrive 21:00     # odds for one moment
  python crossing_sim.py --day Thu                     # hour-by-hour table for Thursday
  python crossing_sim.py --week                        # full 7 x 24 grid -> weekly_results.csv
  python crossing_sim.py --calibrate                   # refit parameters to observed waits
  python crossing_sim.py --live --arrive 18:30         # today, with live train delays
"""
import argparse
import datetime as dt
import json
import re
import time

import numpy as np
import pandas as pd

DAY = 1440
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Calibrated (see --calibrate) to: single-train wait < 5 min, bad (p90) waits 12-15, worst 15-20
DEFAULTS = dict(
    L_pass=4.0,        # gate-down minutes for a train that runs through
    L_halt=6.0,        # gate-down minutes for a train that stops at Ambli Road
    merge_gap=2.0,     # gate stays down if next closure starts within this many minutes
    delay_shape=2.0,   # gamma shape for day-to-day delay spread (lower = wilder)
    freight_per_day=4.0,
    L_freight=14.0,
    freight_night_share=0.6,  # share of freight between 22:00 and 06:00
)

# --- live mode -------------------------------------------------------------
LIVE_BEFORE = 60          # minutes before the arrival time to look for trains
LIVE_AFTER = 20           # ... and after
# How precisely a live position pins down the time at the crossing. A reported
# delay is not exact: the train still has to cover the remaining distance, the
# report itself is minutes old, and a big delay is less stable than a small one.
# So a live train gets a *normal* spread floored at LIVE_SD_BASE, rather than a
# spread proportional to the delay — which for an on-time train would claim we
# know its crossing time to within seconds.
LIVE_SD_BASE = 2.5        # minutes: the floor on a live train's spread
LIVE_SD_FRAC = 0.25       # + this fraction of the reported delay
LIVE_SD_AGE = 0.08        # + this much per minute since the position was reported
LIVE_MAX_AGE_MIN = 180    # ignore a live position older than this
LIVE_TIMEOUT = 12.0       # seconds per HTTP request
LIVE_PAUSE = 1.5          # seconds between requests, to go easy on the sites
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def load(path="trains.csv"):
    df = pd.read_csv(path, dtype={"train_no": str})
    df["crossing_days"] = df["crossing_days"].fillna("")
    pool = df["avg_delay_min"].dropna().to_numpy(float)
    by_day = {d: df[df["crossing_days"].str.contains(d)].reset_index(drop=True) for d in DAYS}
    return df, pool, by_day


def freight_times(rng, n, night_share):
    hours = np.arange(24)
    night = (hours >= 22) | (hours < 6)
    w = np.where(night, night_share / night.sum(), (1 - night_share) / (~night).sum())
    return rng.choice(hours, size=n, p=w) * 60 + rng.uniform(0, 60, n)


def day_events(rng, trains, pool, p, offset):
    """Closure (start, end) arrays for one calendar day, shifted by offset minutes."""
    avg = trains["avg_delay_min"].to_numpy(float).copy()
    miss = np.isnan(avg)
    avg[miss] = rng.choice(pool, miss.sum())
    # A train on its weekly average: gamma around that average, wide (shape 2 is
    # about +-71%). A train with a live position: normal around the reported
    # delay, with the much smaller spread live_sd() gives it.
    delay = rng.gamma(p["delay_shape"], np.maximum(avg, 1.0) / p["delay_shape"])
    if "live_sd" in trains.columns:
        sd = trains["live_sd"].to_numpy(float)
        on = ~np.isnan(sd)
        if on.any():
            delay[on] = np.maximum(0.0, rng.normal(avg[on], sd[on]))
    t = trains["crossing_min"].to_numpy(float) + delay
    L = np.where(trains["halts_ABD"].to_numpy() == 1, p["L_halt"], p["L_pass"])
    nf = rng.poisson(p["freight_per_day"])
    if nf:
        t = np.concatenate([t, freight_times(rng, nf, p["freight_night_share"])])
        L = np.concatenate([L, np.full(nf, p["L_freight"])])
    return t - (L - 1) + offset, t + 1 + offset


def simulate_day(rng, by_day, pool, p, weekday):
    """Per-minute (wait, n_trains_in_closure) for one replay of `weekday`."""
    i = DAYS.index(weekday)
    s_all, e_all = [], []
    for k in (-1, 0, 1):
        s, e = day_events(rng, by_day[DAYS[(i + k) % 7]], pool, p, k * DAY)
        s_all.append(s)
        e_all.append(e)
    s, e = np.concatenate(s_all), np.concatenate(e_all)
    order = np.argsort(s)
    s, e = s[order], e[order]

    merged = []  # [start, end, n_trains]
    for a, b in zip(s, e):
        if merged and a <= merged[-1][1] + p["merge_gap"]:
            merged[-1][1] = max(merged[-1][1], b)
            merged[-1][2] += 1
        else:
            merged.append([a, b, 1])

    mid = np.arange(DAY) + 0.5
    wait = np.zeros(DAY)
    ntr = np.zeros(DAY, dtype=int)
    for a, b, n in merged:
        if b <= 0 or a >= DAY:
            continue
        lo, hi = max(int(np.floor(a)), 0), min(int(np.ceil(b)), DAY)
        idx = np.arange(lo, hi)
        idx = idx[(mid[idx] >= a) & (mid[idx] < b)]
        wait[idx] = b - mid[idx]
        ntr[idx] = n
    return wait, ntr


def simulate(by_day, pool, p, weekday, reps=2000, seed=0):
    rng = np.random.default_rng(seed)
    W = np.empty((reps, DAY))
    N = np.empty((reps, DAY), dtype=int)
    for r in range(reps):
        wd = weekday if weekday else DAYS[rng.integers(7)]
        W[r], N[r] = simulate_day(rng, by_day, pool, p, wd)
    return W, N


def stats(w, n):
    c = w > 0
    if not c.any():
        return dict(p_closed=0.0, wait_if_closed=0.0, p90_wait_if_closed=0.0,
                    p_wait_over_10_if_closed=0.0, p_multi_train_if_closed=0.0)
    return dict(
        p_closed=c.mean(),
        wait_if_closed=w[c].mean(),
        p90_wait_if_closed=np.percentile(w[c], 90),
        p_wait_over_10_if_closed=(w[c] > 10).mean(),
        p_multi_train_if_closed=(n[c] >= 2).mean(),
    )


def hourly(W, N):
    return pd.DataFrame([dict(hour=f"{h:02d}:00", **stats(W[:, h * 60:(h + 1) * 60].ravel(),
                                                          N[:, h * 60:(h + 1) * 60].ravel()))
                         for h in range(24)])


def lookup(W, N, hhmm, window=2):
    h, m = map(int, hhmm.split(":"))
    t = h * 60 + m
    idx = [(t + k) % DAY for k in range(-window, window + 1)]
    return stats(W[:, idx].ravel(), N[:, idx].ravel())


def nearby_trains(by_day, weekday, hhmm, before=45, after=15):
    """Scheduled trains whose crossing time falls shortly before/after the arrival."""
    h, m = map(int, hhmm.split(":"))
    t = h * 60 + m
    i = DAYS.index(weekday)
    out = []
    for k in (-1, 0, 1):
        d = by_day[DAYS[(i + k) % 7]]
        rel = d["crossing_min"] + k * DAY - t
        sel = d[(rel >= -before) & (rel <= after)].copy()
        sel["mins_vs_arrival"] = rel[sel.index]
        sel["day"] = DAYS[(i + k) % 7]
        sel["day_offset"] = k
        out.append(sel)
    out = pd.concat(out).sort_values("mins_vs_arrival")
    return out[["train_no", "name", "direction", "crossing_time", "crossing_min",
                "mins_vs_arrival", "avg_delay_min", "day", "day_offset"]].reset_index(drop=True)


NEARBY_COLS = ["train_no", "name", "direction", "crossing_time", "mins_vs_arrival", "avg_delay_min"]


# ---------------------------------------------------------------- live status

def _parse_trainspnrstatus(html):
    """Delay from trainspnrstatus.com's running-status page.

    The timetable is server-rendered but the live numbers are not: the page
    POSTs to /api/fetch-live-status with a Cloudflare Turnstile token, which we
    have no way of producing, so in practice this returns None and we fall
    through to the next source. Parsed anyway in case the page starts shipping
    the delay in its HTML again.
    """
    m = re.search(r"(?:late\s*by|delayed\s*by)[\s:]*(\d{1,4})\s*(?:min|mins|minutes)", html, re.I)
    if m:
        return dict(delay_min=float(m.group(1)))
    m = re.search(r"(\d{1,4})\s*(?:min|mins|minutes)\s*late\b", html, re.I)
    if m:
        return dict(delay_min=float(m.group(1)))
    if re.search(r"running\s+(?:on|right)\s+time", html, re.I):
        return dict(delay_min=0.0)
    return None


def _parse_railyatri(html):
    """Delay from railyatri.in's live-train-status page (server-rendered JSON)."""
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    lts = json.loads(m.group(1)).get("props", {}).get("pageProps", {}).get("ltsData") or {}
    if not lts.get("success"):
        return None
    if lts.get("delay") is None:
        # train hasn't started, or nobody has reported it yet
        note = (lts.get("title") or lts.get("new_message") or "no live position").strip()
        return dict(delay_min=None, note=note.rstrip("."))
    return dict(delay_min=float(lts["delay"]),
                at=lts.get("current_station_code"),
                age_min=lts.get("status_as_of_min"),
                run_date=lts.get("train_start_date"))


SOURCES = [
    ("trainspnrstatus", "https://trainspnrstatus.com/runningstatus/{no}", _parse_trainspnrstatus),
    ("railyatri", "https://www.railyatri.in/live-train-status/{no}", _parse_railyatri),
]


def fetch_live(train_nos, timeout=LIVE_TIMEOUT, pause=LIVE_PAUSE, max_age=LIVE_MAX_AGE_MIN,
               sources=SOURCES, verbose=True):
    """{train_no: {delay_min, source, note, ...}} — delay_min is None if unknown.

    Sources are tried in order per train. A source that errors out, or that
    yields nothing for its first few trains, is dropped for the rest of the run
    rather than costing a request (and a pause) per train.
    """
    import requests  # imported lazily so the offline modes need no network deps

    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    tries = {name: 0 for name, _, _ in sources}
    dropped = set()
    out = {}

    for no in train_nos:
        rec = dict(delay_min=None, source=None, note="no live data")
        for name, url, parse in sources:
            if name in dropped:
                continue
            tries[name] += 1
            try:
                time.sleep(pause)
                r = sess.get(url.format(no=no), timeout=timeout)
                r.raise_for_status()
                got = parse(r.text)
            except Exception as e:
                got = None
                rec["note"] = f"{name}: {type(e).__name__}"
                dropped.add(name)  # site-level failure, not a per-train one
            if got and got.get("delay_min") is not None:
                age = got.get("age_min")
                if age is not None and age > max_age:
                    rec["note"] = f"{name}: position {int(age)} min old"
                    continue
                rec = dict(got, source=name, note="")
                break
            if got and got.get("note"):
                rec["note"] = got["note"]
            if name not in dropped and tries[name] >= 3 and not any(
                    v.get("source") == name for v in out.values()):
                dropped.add(name)  # three trains in, still nothing: stop asking
        out[no] = rec
        if verbose:
            d = rec["delay_min"]
            shown = f"{d:+.0f} min ({rec['source']})" if d is not None else f"- ({rec['note']})"
            print(f"  {no}  {shown}", flush=True)
    return out


def live_sd(delay, age_min=0.0, base=LIVE_SD_BASE):
    """Spread to put on a live delay, in minutes."""
    age = 0.0 if age_min is None else max(float(age_min), 0.0)
    return float(np.hypot(np.hypot(base, LIVE_SD_FRAC * float(delay)), LIVE_SD_AGE * age))


def apply_live(by_day, window, live, base=LIVE_SD_BASE):
    """Copy of `by_day` with live delays swapped in for the windowed trains."""
    out = dict(by_day)
    for day in window["day"].unique():
        d = out[day].copy()
        d["live_sd"] = np.nan
        nos = window.loc[window["day"] == day, "train_no"]
        for no in nos:
            rec = live.get(no)
            if not rec or rec["delay_min"] is None:
                continue
            hit = d["train_no"] == no
            d.loc[hit, "avg_delay_min"] = rec["delay_min"]
            d.loc[hit, "live_sd"] = live_sd(rec["delay_min"], rec.get("age_min"), base)
        out[day] = d
    return out


def live_table(window, live):
    """The nearby-train table, with live delay and estimated time at the crossing."""
    rows = []
    for r in window.itertuples():
        rec = live.get(r.train_no, {})
        d = rec.get("delay_min")
        used = d if d is not None else r.avg_delay_min
        est = (r.crossing_min + r.day_offset * DAY + (used if pd.notna(used) else 0.0)) % DAY
        where = rec.get("at") or ""
        age = rec.get("age_min")
        if where and age is not None:
            # railyatri reports a negative age when the position is an ETA
            where = f"{where} (now)" if age <= 0 else f"{where} ({int(age)}m ago)"
        rows.append(dict(
            train_no=r.train_no,
            name=r.name[:18],
            dir=r.direction,
            scheduled=r.crossing_time,
            vs_arrival=int(r.mins_vs_arrival),
            live_delay=("-" if d is None else f"{d:+.0f}"),
            last_seen=where or rec.get("note", "")[:28],
            hist_delay=("-" if pd.isna(r.avg_delay_min) else f"{r.avg_delay_min:.0f}"),
            est_at_crossing=f"{int(est) // 60:02d}:{int(est) % 60:02d}",
        ))
    return pd.DataFrame(rows)


def calibrate(by_day, pool, reps=300):
    """Grid search so single-train waits < 5 min, p90 ~ 13, p99 ~ 18 (observed)."""
    targets = dict(single=3.0, p90=13.0, p99=18.0)
    scale = dict(single=1.0, p90=2.0, p99=2.0)
    res = []
    for L_pass in (4, 5, 6):
        for gap in (1, 2, 3, 4):
            for fr in (0, 2, 4, 8, 12):
                for Lf in (8, 10, 12, 14, 16):
                    p = dict(DEFAULTS, L_pass=L_pass, L_halt=L_pass + 2,
                             merge_gap=gap, freight_per_day=fr, L_freight=Lf)
                    W, N = simulate(by_day, pool, p, None, reps=reps, seed=1)
                    c = W > 0
                    s = dict(p_closed=c.mean(), wait_if_closed=W[c].mean(),
                             single=W[c & (N == 1)].mean(),
                             p90=np.percentile(W[c], 90), p99=np.percentile(W[c], 99))
                    loss = sum(((s[k] - v) / scale[k]) ** 2 for k, v in targets.items())
                    res.append(dict(L_pass=L_pass, merge_gap=gap, freight_per_day=fr,
                                    L_freight=Lf, loss=loss, **s))
    return pd.DataFrame(res).sort_values("loss")


def run_live(by_day, pool, p, arrive, weekday=None, reps=2000,
             before=LIVE_BEFORE, after=LIVE_AFTER, live_base_sd=LIVE_SD_BASE,
             timeout=LIVE_TIMEOUT, pause=LIVE_PAUSE, max_age=LIVE_MAX_AGE_MIN):
    """Today's odds at `arrive`, with live delays for the trains due around then."""
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
    weekday = weekday or DAYS[today.weekday()]
    window = nearby_trains(by_day, weekday, arrive, before=before, after=after)

    print(f"Live run for {weekday} {today.isoformat()}, arriving {arrive} "
          f"(window {arrive} -{before} / +{after} min)")
    if window.empty:
        print("No scheduled trains in the window; running on freight + schedule only.\n")
        live = {}
    else:
        nos = list(dict.fromkeys(window["train_no"]))
        print(f"Fetching live status for {len(nos)} train(s):")
        live = fetch_live(nos, timeout=timeout, pause=pause, max_age=max_age)
        print()

    by_day_live = apply_live(by_day, window, live, live_base_sd) if not window.empty else by_day
    W, N = simulate(by_day_live, pool, p, weekday, reps=reps)
    st = lookup(W, N, arrive)

    n_live = sum(1 for r in live.values() if r["delay_min"] is not None)
    print(f"At the crossing, {weekday} {arrive}  ({n_live} of {len(live)} nearby trains on live data)")
    print(f"  P(gate closed)            {st['p_closed'] * 100:5.1f} %")
    print(f"  expected wait if closed   {st['wait_if_closed']:5.1f} min")
    print(f"  p90 wait if closed        {st['p90_wait_if_closed']:5.1f} min")
    if window.empty:
        return W, N, window, live
    print("\nNearby trains (vs_arrival < 0 = reaches the crossing before you):")
    print(live_table(window, live).to_string(index=False))
    return W, N, window, live


def fmt(d):
    return {k: (round(float(v), 3) if isinstance(v, (float, np.floating)) else v) for k, v in d.items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trains", default="trains.csv")
    ap.add_argument("--reps", type=int, default=2000, help="simulated replays per weekday")
    ap.add_argument("--day", choices=DAYS)
    ap.add_argument("--arrive", help="HH:MM")
    ap.add_argument("--week", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--live", action="store_true",
                    help="today, with live delays for the trains due around --arrive")
    ap.add_argument("--live_before", type=int, default=LIVE_BEFORE)
    ap.add_argument("--live_after", type=int, default=LIVE_AFTER)
    ap.add_argument("--live_sd_base", type=float, default=LIVE_SD_BASE,
                    help="minutes; floor on the spread given to a live delay")
    ap.add_argument("--live_max_age", type=float, default=LIVE_MAX_AGE_MIN,
                    help="minutes; ignore a live position older than this")
    ap.add_argument("--live_timeout", type=float, default=LIVE_TIMEOUT)
    ap.add_argument("--live_pause", type=float, default=LIVE_PAUSE)
    for k, v in DEFAULTS.items():
        ap.add_argument(f"--{k}", type=float, default=v)
    a = ap.parse_args()

    df, pool, by_day = load(a.trains)
    p = {k: getattr(a, k) for k in DEFAULTS}

    if a.live:
        if not a.arrive:
            ap.error("--live needs --arrive HH:MM")
        run_live(by_day, pool, p, a.arrive, weekday=a.day, reps=a.reps,
                 before=a.live_before, after=a.live_after,
                 live_base_sd=a.live_sd_base, timeout=a.live_timeout,
                 pause=a.live_pause, max_age=a.live_max_age)
    elif a.calibrate:
        res = calibrate(by_day, pool)
        res.to_csv("calibration.csv", index=False)
        print(res.head(10).round(2).to_string(index=False))
    elif a.week:
        frames = []
        for d in DAYS:
            W, N = simulate(by_day, pool, p, d, reps=a.reps, seed=DAYS.index(d))
            hr = hourly(W, N)
            hr.insert(0, "day", d)
            frames.append(hr)
        wk = pd.concat(frames)
        wk.to_csv("weekly_results.csv", index=False)
        print(wk.pivot(index="hour", columns="day", values="p_closed")[DAYS].round(2).to_string())
    elif a.day:
        W, N = simulate(by_day, pool, p, a.day, reps=a.reps)
        if a.arrive:
            print(f"{a.day} {a.arrive}:", fmt(lookup(W, N, a.arrive)))
            print("\nTrains scheduled near then (mins_vs_arrival < 0 = before you):")
            print(nearby_trains(by_day, a.day, a.arrive)[NEARBY_COLS].to_string(index=False))
        else:
            print(hourly(W, N).round(3).to_string(index=False))
    else:
        ap.print_help()
