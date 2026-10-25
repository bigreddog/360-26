# Canarias 360 · Racer roadbook

A downloadable, self-contained HTML app based on the 254.074 km candidate GPX from Gáldar to Tejeda. It combines 29 terrain sections, five checkpoint stages, personal pacing and resupply opening windows.

**Open [`index.html`](index.html) in a browser**, or download it to your phone. The route, profile, shop data, notes and calculations work without a connection. Street-map tiles, calls and business websites require internet. All dependencies and the original GPX download are embedded in that HTML file.

![Roadbook desktop preview](docs/screenshots/desktop.png)

## Your race plan

- Start: **Wednesday 4 November 2026, 09:00**, Atlantic/Canary.
- Final limit: **101 hours**, Sunday 8 November at 14:00.
- Default net daily progress: **85 / 70 / 60 / 50 km**, allowing for fatigue after the first day. These targets already include normal sleep, meals and race-base stops.
- Default projection: **Sunday 03:45**, about **10h 15m spare**.
- Slower **80 / 65 / 55 / 45 km** scenario: approximately **Sunday 13:50**, leaving only about ten minutes.

Each 24-hour block is distributed using distance plus ascent effort. Daily geographic quotas remain exact, rather than applying a constant kilometre-per-hour speed to every climb. The partial final day uses its proportion of the last daily quota. The last quota repeats if more than four days are needed.

Edit daily targets, add extra delay, or re-anchor future ETAs to your actual distance and elapsed time. The arrival window uses ±5 km on each daily target; it is a scenario range, not a statistical confidence interval.

## What is included

- Section distance, gain/loss, ending elevation, arrival time and day/night indication.
- Five checkpoint-stage summaries and final cut-off margin.
- **353 mapped places** near the route, including shops, bakeries, cafés, restaurants and water points. **102 have published hours; 11 operator schedules were checked directly.**
- Opening checks for the actual arrival date, including split sessions, overnight hours and Sunday closures. Conditional/seasonal expressions that cannot be evaluated conservatively stay unknown.
- Approximate walking detours along the mapped pedestrian network to each venue's vicinity; the final entrance is not surveyed.
- Opening status at your planning ETA and across the full arrival window, next opening/wait, source links and phone numbers where available.
- Filters by type, known hours, owner evidence, saved places, distance ahead and walking detour.
- Editable confirmed hours, personal notes, local saving, JSON plan import/export, portable HTML save, GPX download, section CSV and print layout.
- Offline route/map overlays, with optional online OSM street tiles.

Access is treated as resolved. This app uses the existing candidate course; it does not change its geometry.

## Using resupply information

"Listed open" means the stored weekly schedule covers the modelled arrival time. It does not confirm stock, kitchen service or a one-off closure. Restaurant opening hours do not establish kitchen hours. Unknown hours stay unknown. Water-point operability is unverified. Fuel stations without a separately established shop are not counted as food stops.

Shop ETAs include an estimated outward detour at 3 km/h plus a climb allowance. The finish model does **not** automatically add extra detours, queues, shopping or opening-time waits beyond your net daily targets; put additional time in **Extra delay ahead**. An opening after the final race limit is explicitly marked.

Race-base services and intermediate closing times follow the official event roadbook. Only the supplied final 101-hour limit is modelled here.

## Evidence and elevation

POIs come from an OpenStreetMap snapshot retrieved 25 October 2026, spatially filtered against the candidate track and its pedestrian graph. Operator SPAR pages provide current coordinates and weekly schedules for the checked stores. An older generic Tejeda SPAR POI was suppressed as a probable duplicate of the owner-listed store, whose current hours take precedence. Evidence and this decision are in [`data/roadbook_data.json`](data/roadbook_data.json), and can be downloaded from the app.

Opening and location evidence is attached to each place. Sparse map data is not proof that no other service exists. Operator hours are checked against source pages, not by telephone.

Elevation uses the candidate's original Mapzen/AWS Skadi DEM samples, resampled every 25 m with Gaussian sigma 50 m. Section ascent/descent uses differences of one cumulative smoothed profile, so section totals reconcile with approximately **+11,939 / −10,996 m**. This differs slightly from summing stages smoothed independently. Source GPX checksum is verified on every build; full point geometry is preserved on the map and in the GPX download.

## Build and test

No npm dependencies are required.

```sh
python3 scripts/build.py
node tests/engine.test.js
```

The generated `index.html` is deterministic and has no runtime fetch dependency. Python 3.12 and Node 24 were used. There are 18 engine/data tests covering exact daily quotas, fatigue/finish margins, progress anchoring, split and overnight hours, Sunday closure, unknown/seasonal rules, fuel-shop separation, route-axis integrity and reconciled section totals.

Browser QA uses Playwright with system Chromium. In one terminal, serve this repository:

```sh
python3 -m http.server 8787 --bind 127.0.0.1
```

Then, in another:

```sh
python3 -m pip install playwright
python3 tests/browser_test.py
```

The browser checks block all non-local requests to verify operation without external resources. They cover desktop/mobile layout, filters, notes, safe text handling, opening overrides, offline HTML export/reopen, interactive map/sections and byte-identical GPX download. Test summaries are in `docs/`.

To host with GitHub Pages, select `main` and the repository root in the repository's Pages settings. No hosting or external account is needed for the downloaded HTML.

## Data and software attribution

- Map and POI data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL 1.0. Source queries and ordered place evidence are included with the data.
- Checked shop schedules and coordinates: [SPAR Gran Canaria store pages](https://spargrancanaria.es/tiendas/), linked individually in the app. Factual schedules are normalised to weekly patterns.
- DEM: Mapzen Terrain Tiles / AWS Skadi composite elevation tiles; [Joerd documentation](https://github.com/tilezen/joerd/tree/master/docs).
- Leaflet 1.9.4, BSD-2-Clause; bundled under `vendor/` with its license.
- Day/night markers: Astral calculation for the island centre, not terrain-shadow or weather predictions.

Settings and notes are stored only in your browser or your exported plan. The committed app contains no personal progress or notes.
