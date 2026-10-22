# Thaltej crossing: data notes

Crossing: 23.058006, 72.503175. That's 1.13 km NE of Ambli Road station (ABD), between ABD and Chandlodiya (CLDY), on the Ahmedabad–Viramgam main line.

## Files
| File | What it is |
|---|---|
| build_trains.py | All train data typed in one place; builds trains.csv |
| trains.csv | 110 scheduled passenger trains, with the weekday(s) and time each reaches the crossing |
| crossing_sim.py | The simulation (see its docstring for commands) |
| weekly_results.csv | 7 days × 24 hours: P(closed), wait if closed, p90 wait, P(wait > 10), P(multi-train) |
| calibration.csv | Parameter grid search vs your observed waits |
| requirements.txt | numpy, pandas, requests (requests is only needed for --live) |
| gate_template.html | The phone web app's source; `/*__SCHEDULE__*/` is where the timetable goes |
| gate.html | Built page (template + timetable), published as an Artifact |
| web_data.py | Builds gate.html, and dumps the schedule / live-delay JSON |

## trains.csv columns
- crossing_time / crossing_min: scheduled time at the crossing
- crossing_days: weekdays the train reaches the crossing (already shifted from origin run days)
- halts_ABD: 1 if it stops at Ambli Road (longer closure)
- ref_point / ref_time / day_no_at_ref / origin_days: what the crossing time and days were derived from
- avg_delay_min: 7-day average delay, known for 20 trains; the rest are sampled from those 20

## How crossing days were computed
A train listed as running Wed, Fri from its origin, reaching Ahmedabad on day 2, crosses on Thu, Sat. Spot checks against erail's station-level days all matched (22989 Thu/Sat, 22990 Fri/Sun, 14311 Wed/Fri/Sun, 20937 Wed/Sun).

## Offsets to the crossing
- down (ADI → VG): ADI dep +22, SBT dep +12, CLDY dep +5, ABD arr −2
- up (VG → ADI): VG dep +35, CLDY arr −5, ABD dep +2

## Calibrated parameters (fit to your experience: one train < 5 min wait, bad waits 12–15, worst 15–20)
- Through train closes the gate 4 min; a train stopping at Ambli Road, 6 min
- Gate stays down if the next train is due within 2 min of reopening
- About 4 freight trains a day at about 14 min each, 60% of them at night. **This is a fitted guess, not data.**

## Known weak spots
- Freight (no public data)
- Delays are 7-day averages, and only 20 trains have their own
- ixigo listed 20938 at CLDY 17:30, which conflicts with its own VG time; erail's CLDY 23:05 is used instead
- Seasonal specials (09xxx) dropped because erail no longer lists them

## Live mode
`python crossing_sim.py --live --arrive 18:30` uses today's weekday, takes the trains due at
the crossing from 60 min before to 20 min after that time, looks up how late each one is
running right now, and re-runs the simulation with those delays in place of the weekly
averages. A live delay is also given a much tighter spread: a normal with sd =
sqrt(2.5^2 + (0.25*delay)^2 + (0.08*age_of_sighting)^2) minutes, against the weekly average's
gamma(shape 2) at about +-71%. The 2.5 min floor matters -- scaling the spread with the delay
would say an on-time train's crossing time is known to within seconds, which it is not: the
train still has to run the remaining distance and the sighting is already minutes old.

- trainspnrstatus.com is tried first, but its running-status page only renders the
  timetable: the live numbers come from a POST to its `/api/fetch-live-status`, which needs
  a Cloudflare Turnstile token. So in practice it yields nothing and the fallback,
  railyatri.in/live-train-status/<no>, supplies the delay (server-rendered in `__NEXT_DATA__`:
  current station, delay in minutes, how old the position is). A source that errors, or that
  comes up empty for its first three trains, is dropped for the rest of the run.
- 1.5 s between requests, 12 s timeout, both tunable (`--live_pause`, `--live_timeout`).
- Positions older than `--live_max_age` (default 180 min) are ignored.
- A train whose run has not started yet has no live delay and keeps its historical average.
  This is normal for crossing times several hours out: asking about 03:20 mostly returns
  "train starts at 19:10". Live mode is most useful within an hour or two of now.

## Sources
- Timings and run days: ixigo.com/trains/<number> (Oct 2026), erail.in ADI↔VG listings
- Delays: trainspnrstatus.com/running-history/<number>
- Gate closure duration context: ETV Bharat, Sept 2026
- Live delays: railyatri.in/live-train-status/<number> (crowd-sourced + NTES, per their disclaimer)

## The phone app
`python web_data.py --build` splices trains.csv into gate_template.html and writes gate.html,
which is published as a Claude Artifact and opened from a phone.

The whole simulation is **ported to JavaScript and runs in the browser**, so the page recomputes
against the device clock (pinned to Asia/Kolkata) rather than serving a stale snapshot. It is the
same model: same parameters, same gamma delays, same closure merge, checked against crossing_sim.py
to within Monte Carlo noise. It runs 4,000 replays over a 91-minute window instead of a whole day,
pre-filtering to the ~20 trains that could reach the window, which takes 30-60 ms.

Live delays cannot be fetched by the page -- an Artifact may not call out to railyatri -- so they
arrive through the artifact's shared database: run `python web_data.py --live --hours 3` and paste
the JSON into the page's **Sync live delays** sheet. Everyone who opens the page then sees it. A
snapshot older than 3 h is ignored and the page falls back to weekly averages, saying so.
