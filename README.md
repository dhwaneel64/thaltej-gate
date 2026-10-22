# Thaltej Gate

How likely is it that the level crossing at Ambli Road is closed right now, and how long
would you sit there? A Monte Carlo model of 110 trains, plus live running status.

- **`docs/`** — the website. A single page that runs the whole simulation in the browser.
- **`crossing_sim.py`** — the same model as a command-line tool.
- **`web_data.py`** — builds the site, and fetches the live-delay snapshot it reads.

---

## Putting it online (free, permanent link)

The site is plain static files. Any static host works; **GitHub Pages** is the one worth
using, because it also runs the live-delay refresh for free.

### GitHub Pages — recommended

```bash
# from this folder, with the repo already committed:
git remote add origin https://github.com/<you>/thaltej-gate.git
git push -u origin main
```

Then, in the repo on github.com:

1. **Settings → Pages** → Source: *Deploy from a branch* → Branch: `main`, Folder: **`/docs`** → Save.
2. **Settings → Actions → General** → Workflow permissions: **Read and write** → Save.
   (Without this the refresh job cannot commit new delays.)
3. **Actions** tab → *Refresh live delays* → **Run workflow**, to fill in the first snapshot.

Your link, a minute later: `https://<you>.github.io/thaltej-gate/`

The repo has to be **public** for Pages and unlimited Actions minutes on the free plan.
Nothing in here is sensitive — it is a train timetable.

### Anything else

Drag the `docs/` folder onto [app.netlify.com/drop](https://app.netlify.com/drop) or
[tiiny.host](https://tiiny.host) and you get a link in about ten seconds. The page works
fine, but nothing refreshes `live.json`, so it falls back to 7-day averages after a few
hours — which it says on screen. Re-upload the folder to refresh it.

---

## How the live delays stay fresh

`.github/workflows/refresh-live.yml` runs every 15 minutes on GitHub's runners: it looks up
the current delay of every train due at the crossing in the next 4 hours, writes
`docs/live.json`, and commits only if something changed. The page re-reads that file on load
and every 4 minutes.

Two things to know. GitHub **disables scheduled workflows after 60 days of no commits** to
the repo — push anything to wake it up. And cron on the free tier is best-effort, so a
15-minute schedule often lands every 20–30; the page always shows how old its data is, so a
late run degrades honestly rather than lying.

If railyatri ever blocks the runner's IPs, the job still succeeds and simply reports no live
trains — the page carries on with averages.

To refresh by hand:

```bash
python web_data.py --live --hours 4 > docs/live.json
git commit -am "live delays" && git push
```

---

## Working on it locally

```bash
pip install -r requirements.txt

python web_data.py --site        # rebuild docs/index.html after editing site_template.html
cd docs && python -m http.server 8000
# http://127.0.0.1:8000  — serve it, don't open the file directly, or live.json won't load
```

`docs/index.html` is **generated**. Edit `site_template.html` and rebuild; the build only
splices the timetable JSON into the `/*__SCHEDULE__*/` placeholder.

The page is three files. `docs/model.js` is the simulation, kept separate so the look can be
rewritten without touching arithmetic that has been checked against `crossing_sim.py`.
`docs/vendor/three.min.js` is three.js r149, vendored rather than loaded from a CDN so the
site has no third-party dependency and still works offline. `site_template.html` is
everything else: the scene, the scroll choreography and the type.

Both scripts are classic (non-module) and therefore **share one global scope** — declaring the
same `const` in both is a SyntaxError that silently kills the whole page. If you add a
top-level name to either, check it is not already in the other.

## The command-line tool

```bash
python crossing_sim.py --live --arrive 18:30     # today, with live delays
python crossing_sim.py --day Thu --arrive 21:00  # any weekday, historical averages
python crossing_sim.py --week                    # 7 x 24 grid -> weekly_results.csv
python crossing_sim.py --calibrate               # refit parameters to observed waits
```

The browser port and the Python model agree to within Monte Carlo noise; if you change one,
change the other. `data_notes.md` has the data sources, the offsets to the crossing, and the
known weak spots — the biggest being that **freight is a fitted guess, not data**.
