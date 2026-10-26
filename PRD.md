# Canarias 360 Racer Roadbook — Product Requirements

Status: specification of the current product and required maintenance workflow  
Repository: [bigreddog/360-26](https://github.com/bigreddog/360-26)  
Application: [bigreddog.github.io/360-26](https://bigreddog.github.io/360-26/)  
Baseline: official 2026 GPX + 29 organiser waypoints/PDF, 12/24-hour forecasts, app installation and remembered map settings; updated 26 October 2026

## 1. Purpose and user

Provide a practical race companion for a runner completing Canarias 360 over several days. The runner must quickly understand the next checkpoint, remaining terrain, current leg, likely resupply opportunities, weather at the places they will reach, and the direction of the upcoming trail.

The primary device is an ordinary Android phone using Chrome. The interface must remain usable outdoors, with tired eyes, poor connectivity and sleep deprivation. iPhone Safari is also supported, subject to browser sensor limitations. The runner must be able to use manual progress when GPS is unavailable.

This is a personal, static web application with a downloadable, self-contained HTML backup. No account, application backend or remote tracking service is required.

## 2. Race and route baseline

| Item | Current baseline |
| --- | --- |
| Race start | Wednesday 4 November 2026, 09:00, Atlantic/Canary |
| Final time limit | 101 hours; Sunday 8 November 2026, 14:00 |
| Published target distance | 254.11 km |
| Official GPX distance | 249.37268507008034 km, displayed as 249.4 km; the PDF still lists 254.11 km |
| Archived candidate | 254.07419869370452 km; retained for comparison |
| Roadbook elevation | Approximately +11,861 / −10,940 m, using the method below |
| Original ascent estimate | Approximately 10,500 m with substantial uncertainty; do not force the calculated total to match it |
| Default daily distances | 85 / 70 / 60 / 50 km; later days reflect fatigue |
| Stronger / slower presets | 90 / 75 / 65 / 55 km and 80 / 65 / 55 / 45 km |
| Route structure | 47 legs, 48 anchors, nine checkpoint stages; four sleeping lifebases |
| Resupply dataset | 337 places; 95 with published hours, nine with operator-checked schedules |
| Canonical GPX | [`routes/canarias360_official_2026.gpx`](routes/canarias360_official_2026.gpx) |
| Canonical roadbook data | [`data/roadbook_data.json`](data/roadbook_data.json) |

The organiser's published distance and the supplied track's actual distance are separate quantities. Do not stretch the track or change geography to match the PDF.

| WP | Official checkpoint | Actual GPX km | PDF km where supplied | Cut-off, Canary time | Service |
| --- | --- | ---: | ---: | --- | --- |
| 1 | Gáldar | 0.000 | 0.00 | Start Wed 4, 09:00 | Start |
| 4 | Artenara | 34.248 | — | Wed 4, 19:55 | Aid station; **no sleeping lifebase** |
| 9 | Aserrador | 63.530 | — | Thu 5, 05:35 | Cut-off control |
| 10 | Cercados de Araña | 77.594 | 79.20 | Thu 5, 10:05 | Life base 1 |
| 15 | Parque Sur | 119.576 | 121.68 | Fri 6, 01:35 | Life base 2 |
| 20 | Santa Lucía | 160.792 | 163.60 | Fri 6, 19:40 | Life base 3 |
| 21 | La Pasadilla | 179.973 | — | Sat 7, 05:50 | Cut-off control |
| 26 | Santa Brígida | 209.212 | 212.99 | Sat 7, 18:30 | Life base 4 |
| 28 | Balcón de Zamora | 231.629 | — | Sun 8, 06:10 | Cut-off control |
| 29 | Tejeda | 249.373 | 254.11 | Sun 8, 14:00 | Finish |

The raw source’s elevation-adjusted 3D length is approximately 253.956 km. This illustrates why distance conventions matter; the organiser’s exact 254.11 km calculation is not supplied. The application retains its consistent horizontal geodesic convention.

The application uses actual official GPX chainage for progress, legs, forecasts and matching. Artenara is an official checkpoint without a sleeping lifebase, per the runner's clarification. Control points do not imply food or sleep services. All nine cut-offs are now supplied by the PDF and must be shown against the runner's projected arrival.

### Route evidence and scope

Canonical sources are the runner-uploaded root files [360_2026_Total.gpx](360_2026_Total.gpx), [360_2026_Waypoints.gpx](360_2026_Waypoints.gpx), and [the official 2026 roadbook PDF](docs/evidence/ROAD_BOOK_2026_-ESP_ENG_FRA.pdf). Combine track and waypoints before processing. The source track contains 92,660 points; the combined canonical download removes 1,116 consecutive duplicate positions, retains the other 91,544 points unchanged, and includes all 29 supplied waypoint locations with numbered English instructions. Zero waypoint-elevation placeholders are replaced by nearby official track elevations. Original uploads remain unchanged. An old internal software timestamp is not treated as evidence of the course edition.

The prior candidate remains archived in [routes/canarias360_best_candidate.gpx](routes/canarias360_best_candidate.gpx) and [data/candidate_roadbook_reference.json](data/candidate_roadbook_reference.json). The [comparison report](docs/route-comparison.html) documents a 4.702 km reduction and similar smoothed ascent (11,861 m official vs 11,939 m candidate). At 25 m sampling, 68.57% of the official course lies within 30 m of the candidate; reverse overlap is 66.99%. These are geometric overlap measures, not probabilities.

The supplied official source supersedes the inferred candidate. Historical GPX files and organiser profile artwork remain research evidence, rather than substitutes for the new geographic track. Preserve provenance and unresolved differences, including the PDF's 254.11 km versus measured 249.373 km. Access flags remain **resolved** per user instruction. Do not introduce invented route or resupply connectors. The PDF's rough-sea coastal alternative and collapsed-trail warning are instructions; no replacement geometry was supplied, so the app must not invent a diversion.

## 3. Product principles and scope boundaries

- Put the next actionable information first. Use short labels, large distances, clear units and progressive disclosure.
- Body and form text should be 18 px; supporting text at least 16 px. Primary controls must have touch targets of at least 48 px.
- Fit 320–430 px portrait screens, landscape and enlarged text without horizontal scrolling. Avoid wide tables in racer-facing views.
- Preserve keyboard access, visible focus, readable contrast and text equivalents for icons and status colours.
- Keep daily progress settings collapsed by default. Preserve open place/leg disclosures and focus during GPS refreshes.
- Maintain four primary tabs: **Race**, **Legs**, **Resupply**, **Map**.
- Do not restore saved notes, bookmarks, custom hours editing, plan JSON import/export, the “Little spare time in the slower scenario” panel, or Beaufort indicators.
- Do not add camera access, live-video overlays, photorealistic terrain or an unnecessary runtime framework.

## 4. Functional requirements

### 4.1 Race progress and pacing

The global progress controls must remain available from every tab. The runner can enter **Current km** manually, enable GPS, or tap **Sync location & time** to link position and the current race clock.

GPS is opt-in on each session. A fresh, usable fix updates progress through segment projection on the ordered route. Weak, stale, off-route or unresolved overlapping-route fixes must not overwrite the last usable progress. Show an understandable status and retain manual fallback. Distinguish physical GPS position from matched route position and distinguish straight-line distance from walking distance.

Sync must request GPS when necessary, wait for a usable route match, calculate elapsed time from the race start, and anchor subsequent ETAs. Keep the pre-start schedule at Wednesday 09:00. After the final limit, report actual elapsed time and lateness without resetting or capping the clock. Switching GPS off freezes the last anchor; editing manual timing ends automatic clock linkage. Reopening restores settings and progress without restarting sensors.

The fatigue model allocates each 24-hour block using distance plus ascent effort, while retaining its daily distance quota. The final quota repeats if more days are needed. Ordinary meals, sleep and stops are included in daily targets. **Extra delay** adds further time. Opening-hour ETA scenarios use daily quotas ±5 km; they are scenarios, not statistical confidence intervals.

The official course's default projected finish is approximately Sunday 01:30, with 12 h 30 m spare. The slower preset is approximately Sunday 11:20, with 2 h 40 m spare. Recalculate these examples for a replacement route; do not hardcode them into the model. Retain a warning when a plan actually misses the final limit. Use the nine supplied checkpoint cut-offs. Do not infer additional services or other unpublished barriers.

### 4.2 Race tab

Lead with a prominent next-checkpoint panel: dark green, gold accent, large checkpoint name, distance remaining, ascent/descent remaining and planned arrival. It must be easy to distinguish from surrounding panels. Include checkpoint service type, the official cut-off and planned margin or lateness. Show the next numbered PDF route instruction and any active explicit-distance warning; fold remaining notes before that checkpoint and the full 29-waypoint list. Preserve open lists during GPS updates. Include PDF source/page references. Never label Artenara as a sleeping base. Completion must display the finish state.

Place **Weather ahead** immediately above **Route profile**. Show the full elevation profile with checkpoint and progress markers; tapping it selects the corresponding leg on the map. Provide folded stage details and the food-gap summary.

Food gaps compare listed-open shops at the runner's planned ETA within the current 1.1 km walking threshold. Unknown schedules and cafés are excluded from this calculation. State that other services may exist; absence from the dataset is not proof of no resupply.

### 4.3 Legs tab

Display legs in race order with start/end names and kilometres, distance, ascent, descent, end elevation, planned arrival and map access.

- Mark a leg complete at its exact end distance; show a completion tick.
- Highlight exactly one current leg before the finish, with distance remaining and a progress bar.
- At a shared boundary, complete the arriving leg and activate the next. At the finish, complete all legs and leave none active.
- Derive marks from current progress, not permanent visit flags, so backtracking or manual correction updates them correctly.
- Show completed count and a **Go to current leg** action; at the finish it links to the final leg.
- Use discreet SVG icons and visible counts for shops, cafés/meals and water points within 500 m walk each way. These indicators are independent of Resupply-tab filters.
- Expand icons into names, route kilometres, walking detours, planned opening status and map actions. Mark points behind progress as **Passed on route**, which does not claim a visit or purchase.
- Assign endpoint POIs to the arriving leg once; include start-line POIs in the first leg. Account for rounding at the final route kilometre.
- Keep stop details collapsed initially and preserve expanded lists during live updates. Show a clear empty state where no mapped nearby resupply exists.

### 4.4 Resupply tab

Show six matching places initially, ordered by route progress, with a **Show next 6 places** action. Lead with name/type, distance ahead or behind along the route, walking detour, arrival and opening status. Keep map and call as the main actions. Place schedule, sources, ETA scenarios and separate GPS straight-line distance in **Hours & details**.

Search is visible; filters are initially collapsed. Defaults are food/drinks, only places ahead, within 500 m walking distance each way, any opening status. Support shops/bakeries, cafés/meals, water and all places; walking thresholds 250/500/1,000/1,600 m; listed-open, operator-checked and unknown hours.

Use actual mapped businesses and source-backed locations. Operator hours take precedence over older generic listings where the identity is established. Preserve source dates and deduplication decisions. Unknown or unsupported seasonal/holiday schedules stay unknown. Handle split sessions, overnight opening and Sundays. Show the next opening and waiting time when calculable. Do not equate fuel stations with confirmed shops, restaurants with available kitchen service, or mapped taps with working water supplies.

Shop ETAs include the outward detour. The finish model does not silently add every shopping trip, queue or wait; the runner can add delay. Do not present approximate final-entrance distances as a surveyed path.

### 4.5 Map and location

Use bundled Leaflet to show the official polyline, filtered resupply pins, checkpoint markers, selected legs and mapped stop approaches. Display actual GPS position plus accuracy and provide centre-on-me, whole-route and progress actions. Label the official course, checkpoint numbers/types and organiser waypoint notes clearly.

Route geometry, pins and selection must work without online tiles. Street-map tiles are on by default when the Map view opens and need internet. Persist the on/off choice as a boolean `streetMap` in the existing plan settings, restore it before map initialization, and preserve it in saved HTML. Older settings without this field default to on. Do not request tiles before the map opens or when the saved preference is off. Tile failure must not disable route geometry or pins; do not bulk-cache OSM tiles. Never substitute straight-line proximity for a pedestrian route to a shop.

### 4.6 Weather ahead

Provide only **12 / 24 hour** views, with **12 hours** selected initially, for the locations and heights the runner is projected to reach. Use the existing fatigue/ascent pacing model and latest progress/time anchor. Extra delay holds projected position before travel resumes. Before the start, use the race schedule or a later explicit elapsed anchor; during the race, begin at the current clock time and last route progress.

Request up to 25 hourly positions (start plus 24 hours) in a single Open-Meteo multi-location request, using projected latitude, longitude and the GPX-derived roadbook elevation. Include an exact fractional finish endpoint when needed and stop the outlook at the finish. Do not use only the start-town forecast, a single island-wide forecast, or today's weather in place of unsupported race dates.

Show weather icons and text, temperature and feels-like ranges, approximate moving-route rain in mm, maximum individual hourly rain chance, peak hourly wind and gusts in **km/h**, and highest/lowest route terrain. Terrain ranges must include crests between hourly samples. Expand timed route stops for places, kilometres, elevations and detailed conditions. Use night variants where appropriate.

**Wind convention:** the provider's degrees and **From N / NE / …** labels describe the source. The north-up arrow shows the direction the air travels: `arrow bearing = (source bearing + 180) mod 360`. A northerly wind therefore points south. Apply this convention in both summary and stop cards. Pair summary direction with the strongest hourly wind sample; peak gusts may occur elsewhere. Calm conditions have no prevailing-direction arrow; missing direction remains unavailable. Do not add Beaufort scales.

Use hourly Celsius/km/h/mm fields, UNIX times and GMT requests, displayed in Atlantic/Canary time. The current API request uses explicit start/end hours; do not add a mutually exclusive `forecast_days` parameter. Respect the provider's approximately 16-day forecast window and label distant, partial or unavailable forecasts. Never invent missing values or extrapolate beyond response times.

Rain totals are approximate sums along the moving route, excluding the hour before outlook start and weighting a partial finish hour. A maximum hourly probability is not a combined whole-window probability. Elevation downscaling does not make exposed-ridge wind or local mountain weather certain.

Refresh normally every 30 minutes while the Race tab is visible, after relevant plan changes or explicit time/location sync, and after substantial progress. Reuse the same trajectory when switching horizons and rate-limit failed requests. Cache fetched forecasts with route identity, original positions, dates and fetch time. Use cache schema version 2 and `canarias360-weather-v2`; do not reuse the former 18-hour cache as a full-day forecast. Switching between 12 and 24 hours must use the same newly calculated 24-hour trajectory without another request. Mark offline/stale data, and suppress expired numerical outlooks. Saved HTML should include the current forecast snapshot. Attribute Open-Meteo and its licence.

### 4.7 Trail Vision

Open **Trail Vision** from the Map tab. Render a first-person perspective preview in a fullscreen dark view using Canvas; no camera, video, WebGL dependency or terrain download is required. Reuse the shared location service and existing settings.

The GPX stays fixed in geographic space. Phone heading and tilt move the camera, not the route. Convert track geometry to local east/north/up metres. Place the eye approximately 1.7 m above interpolated GPX elevation. Show a bright cyan ribbon, actual bends and height changes, current-position reference, horizon/grid, 100 m markers, compass/reference, quality, GPS accuracy, progress, ascent/descent/net change and off-route/out-of-view indications.

Default to compass mode, 500 m ahead and 1× elevation. Offer 100/250/500/1,000 m, vertical scales 1/1.5/2/3×, Recenter, explicit Manual and Follow route modes, and desktop simulation. Recenter only clears view offsets. Vertical exaggeration changes rendering, not reported statistics. Calculate look-ahead by cumulative route distance; resample only the connected local window at roughly 5 m spacing.

Project GPS onto segments fractionally, use previous progress to disambiguate switchbacks and repeated passes, support legitimate backtracking, and warn on ambiguity, poor accuracy, stale fixes or off-route positions. Do not bridge GPX segments or unverified sparse gaps; the current preview conservatively splits point jumps above 400 m. Missing/unreliable elevation must produce a labelled flat preview.

Use quaternion orientation and responsive smoothing, handle screen rotation and Android/iOS permission differences, and avoid an uncomfortable rolled horizon. Label iOS magnetic heading and Android's unverified north reference; no declination model is currently bundled. Do not claim true-north accuracy.

Compass states are **Good**, **Uncertain**, **Unavailable**, **Calibration suggested**. Use available reported quality and corroborating sensor evidence; heading movement or absence alone does not establish a calibration fault. Never invent accuracy percentages. Show the established low-accuracy warning and help when appropriate; the app cannot calibrate the magnetometer itself.

Render only while active and as needed; cap work for ordinary phones, pause in background and clean up subscriptions, timers, observers and Canvas resources on exit. Stop a location watch started by Trail Vision while retaining an independently enabled shared watch.

The local GPX picker is **preview-only** and session-only. It does not replace the race map, progress axis, POIs, weather, checkpoints or GPX download. A full race-route update requires Section 7 below.

### 4.8 Installable app

The hosted HTTPS roadbook must be installable from Android Chrome and launch as a standalone app from its home-screen icon. Provide a web app manifest with stable relative app ID, start URL and scope for `/360-26/`, app name, theme/background colours, and bundled 192/512 px PNG icons including maskable support. Keep orientation unrestricted for portrait and landscape Trail Vision.

Expose **Install app** under **Downloads & tools**. Capture Chrome's install event, prompt only on the runner's tap, handle acceptance/dismissal without blocking the roadbook, and hide the redundant action in standalone mode or after installation. When Chrome does not supply a prompt, show menu instructions: **⋮ → Add to home screen → Install**. On iPhone, explain Safari **Share → Add to Home Screen**. The browser controls native installation eligibility and timing; do not claim the app can force a prompt.

Cache the manifest and icons alongside the HTML for offline app launches. Installation does not grant location or motion permission; preserve all opt-in behaviour and manual fallbacks. Downloaded HTML remains a self-contained backup: remove hosted manifest/icon dependencies from that file and direct installation to the hosted HTTPS app. Verify metadata and prompt handling with browser tests, and record that native installation on physical Android has not been exercised by emulation.

### 4.9 Downloads, evidence and printing

Keep **Downloads & tools** available with:

- A self-contained HTML copy with current plan settings and the latest available dated forecast snapshot. It must reopen with settings folded and GPS off.
- The canonical GPX as an ordered track with elevation and checkpoint waypoints; downloaded bytes must match the canonical file exactly.
- A section CSV containing from/to kilometres, distance, ascent/descent, planned arrival and elapsed time.
- A source/evidence JSON download with route identity, processing notes, source records and place evidence. This is an evidence export, not the removed plan import/export feature.
- A printable roadbook with route-leg information and the next matching resupply places. Preserve readable contrast without background printing and avoid splitting cards where practical.

Show hosted offline-readiness status and explain that online tiles/links and fresh forecasts need connectivity. Do not bundle a runner's personal progress into the committed production page.

## 5. Architecture and data contract

Use plain JavaScript/CSS/HTML and bundled Leaflet. There are no npm runtime dependencies. Keep geometry, forecast and sensor logic isolated and testable; avoid unnecessary dependencies or architectural changes.

| File | Responsibility |
| --- | --- |
| `index.template.html` | Racer-facing markup, primary CSS and embedding placeholders |
| `app.js` | UI, state, shared GPS integration, tabs, legs, downloads and map |
| `engine.js` | Pacing, interpolation, opening hours, leg progress and leg POI assignment |
| `location.js` | Shared opt-in tracker and main-map segment matching |
| `install.js`, `manifest.webmanifest`, `icons/` | Browser install action, scoped app metadata and home-screen icons |
| `weather.js`, `weather.css` | Projected forecast trajectory, API/cache, summary and cards |
| `vision-core.js` | GPX parsing, geometry, matching, elevation and orientation maths |
| `vision.js`, `vision.css` | Trail Vision lifecycle, controls, sensors and renderer |
| `data/roadbook_data.json` | Canonical derived race, route, terrain, POI and evidence data |
| `routes/canarias360_official_2026.gpx` | Canonical combined official track with all 29 numbered instruction waypoints |
| `scripts/update_official_route.py`, `data/poi_sources/`, `data/routing/` | Reproducible comparison, terrain and resupply regeneration with source snapshots |
| `scripts/build.py` | Validates GPX hash and embeds assets/data/GPX into generated `index.html` |
| `sw.template.js` → `sw.js` | Hosted offline navigation cache, versioned from built HTML, manifest and icon content |
| `tests/`, `docs/` | Pure/browser verification, evidence, screenshots and sensor documentation |

`index.html` and `sw.js` are generated, tracked release files. Edit their source files and rebuild; do not maintain a separate hand-edited production copy.

### Canonical data fields

| Field | Required meaning and consistency |
| --- | --- |
| `gpx_sha256` | SHA-256 of the exact canonical GPX bytes; must match the download and embedded GPX |
| `route` | Display/matching/weather `[latitude, longitude]` polyline using original official vertices simplified within 0.75 m; 18,576 points in this revision |
| `track_km` | Full official GPX point-by-point cumulative axis (91,544 entries), used by Trail Vision; distinct from simplified map geometry |
| `route_km` | Cumulative horizontal geodesic kilometres, same length/order as `route`, retaining full-track chainage at selected vertices; zero start and increasing axis |
| `distance_km` | Full route length on that same axis; avoid accumulated display rounding |
| `profile` | Ordered `[km, elevation_m, cumulative_ascent_m, cumulative_descent_m]` samples covering the whole route |
| `gain_m`, `loss_m`, `profile_method` | Totals from that common processed profile and an explicit processing description |
| `checkpoints` | Ten ordered official checkpoint locations, including start, aid, controls, four lifebases and finish; names, WP number, type, actual km, coordinates and published cut-offs |
| `waypoints` | All 29 supplied waypoint locations with original names, numbered English instructions, PDF page, explicit instruction extent where supplied, service type and cut-off |
| `anchors` | Ordered named route locations with actual `km` and `checkpoint` flag |
| `sections` | Consecutive zero-based IDs, names, `from_km`, `to_km`, distance, gain/loss, end height/location, stage and checkpoint flag |
| `pois` | Stable source ID, name/category, coordinates, route km/index, approach distances/geometry/time, opening-hours evidence, contacts and type flags |
| `start`, `timezone`, `limit_hours`, `daylight` | Race-clock context and dated sunrise/sunset data |
| `based_on`, `researched`, `access_assumption`, `sources`, `source_decisions`, `notes` | Source identity, dates, hashes/URLs, decisions and limitations |

The current roadbook uses official GPX elevations, resamples elevation at 25 m, applies a Gaussian filter with sigma 50 m, and sums positive/negative increments on that grid. The stored display profile is reduced to roughly 100 m spacing while retaining the cumulative totals and endpoints. Calculate leg gain/loss by differences of cumulative totals, not by separately smoothing each leg or summing differences of the coarser display elevations. Whole-metre rounding may produce small section-sum differences.

Trail Vision independently uses the GPX elevation with a short local filter. Its 500 m totals need not exactly match the coarser roadbook profile; retain the documented distinction.

## 6. Offline operation, persistence and privacy

The built HTML contains route, GPX, POIs, libraries and preview code. After a successful hosted load, the service worker caches that HTML, the web app manifest and the install icons; navigation tries the network for about 3.5 seconds before fallback. Changing the built HTML, manifest or bundled install icons changes the cache revision. An installed app uses the same offline route/map/preview and settings as the hosted app; new forecasts and street tiles still require network access. Confirm offline readiness before the race. Street tiles and business links are not bundled; forecasts require an initial online request and remain dated when cached.

The app stores plan settings, street-map preference and matched progress under `canarias360-roadbook-v2`; forecasts use `canarias360-weather-v2`. A saved HTML includes an embedded plan and, when present, a forecast snapshot. Do not persist raw GPS fixes, sensor histories or preview-uploaded GPX files. Forecast requests send projected course positions/elevations to Open-Meteo; raw GPS fixes are not sent to an application server.

Downloaded files may restrict GPS and motion permissions. Recommend the cached HTTPS app for live sensors and keep saved HTML as backup. Storage eviction, device clock error and background sensor suspension remain browser limitations.

## 7. Mandatory workflow when the race GPX changes

**Replacing the GPX file alone is not a route update. Updating only its checksum is also insufficient.** The GPX, distance axis, terrain, checkpoints, POIs, weather and Trail Vision must describe the same revision before publishing.

The checked-in `scripts/build.py` remains an **assembler**. The reproducible preparation command is now `scripts/update_official_route.py`, with development dependencies in `requirements-route-update.txt`. It merges both root GPXs, reviews correspondence against `data/official_waypoint_instructions.json`, writes the combined canonical GPX, compares the candidate, rebuilds terrain/legs/checkpoints, and recalculates resupply against the versioned `data/routing/approach_graph.npz` and `data/poi_sources/` snapshots. `way_tags.json.gz` preserves underlying OSM way classifications/access/surfaces. No Python preprocessing dependencies are added to the browser runtime.

The approach graph is clipped to 1,800 m of the current official track and its source hash is checked. A different track must have its graph coverage reviewed/refreshed before regeneration; do not relabel an incomplete corridor cache as complete new-route coverage. Venue final-entrance offsets (up to 100 m) and GPX-to-OSM attachment offsets (at most 3 m) are recorded estimates; only mapped graph edges are drawn. One shortest network attachment per venue is represented, so repeated-pass opportunities are not exhaustively enumerated. Original OSM/operator snapshots remain dated 24–25 October, with approaches recalculated on 26 October.

Do not run the historical `prepare_repo.py` scaffolder against the live app; it would overwrite later features.

The following remains the required maintainer procedure. The implemented preparation script automates the current two-GPX update; it is not an in-browser race GPX uploader. Review and update the PDF transcription when source waypoints or instructions change.

### 7.1 Record and validate the replacement

1. Preserve the previous route revision, source record and validation results in version control. Record the incoming GPX's source URL/file, edition, retrieval date, hash, authoritative status and reason for replacement.
2. Parse real GPX track segments/points and waypoint names. Check coordinate bounds, track order, elevations, repeated passes, zero-length duplicates, gaps and maximum spacing. Preserve actual route order even where it revisits the same location.
3. Resolve checkpoint locations against the replacement track using geography **and checkpoint order**, not nearest point alone. Retain venue ambiguity explicitly where necessary. Preserve organiser target distances separately from newly calculated actual distances.
4. Require a continuous, ordered canonical track for the current whole-race application. The main map/weather data model is a flat polyline: it does not preserve segment breaks. If an incoming GPX has genuine disconnected segments, stop and report the gap, obtain a continuous source, or first extend every downstream consumer to handle segment breaks. Never flatten gaps into artificial straight lines. A Trail Vision gap warning does not fix a bridged main-map track.
5. If normalization is necessary, record exactly what changed, retain the original as evidence, and make the validated normalized GPX the new canonical file. Never smooth geographic bends away, reroute off-trail, or invent elevations. Use a suitable real DEM for missing heights and record source, resolution and processing; if usable heights cannot be obtained, report the affected features as blocked.

### 7.2 Rebuild geometry and terrain

1. Write the canonical route named by `gpx_file` (currently `routes/canarias360_official_2026.gpx`) from the validated merged sources; preserve/check its checkpoint waypoints. The public filename can stay stable, but source identity and checksum must change appropriately.
2. Recompute cumulative WGS84 horizontal geodesic distance from the new point sequence. Produce full `track_km` aligned with the canonical GPX parser, and simplified map `route`/`route_km` arrays retaining those original chainages. Keep full computational precision until display, including repeated passes. If duplicate removal is needed, apply the same documented normalization to the canonical GPX and derived arrays.
3. Recompute the common 25 m elevation grid, 50 m Gaussian smoothing, cumulative gain/loss and reduced display profile, or document a justified revised method. Recalculate total distance/ascent/descent and start/end heights. Do not reuse the previous route's totals.
4. Reproject all checkpoints and named anchors to their correct occurrence on the new route. Remove anchors that are no longer on the course, add meaningful new terrain/town boundaries, and rebuild every leg and stage. Do not scale old kilometres by the new length ratio.
5. Make section IDs consecutive and zero-based: map selection currently indexes `DATA.sections[id]`. Ensure sections partition the entire route without gaps or overlaps, and that stage/checkpoint endpoints reconcile with actual checkpoint positions.
6. Review display assumptions that can become wrong: the current profile's 1,900 m plotting range, fixed leg/stage counts in copy, town names, checkpoint labels, candidate descriptions and example finish times. Update them from the new data as needed.

### 7.3 Recalculate resupply against the new route

1. Download or deliberately reuse a dated OSM place snapshot covering the **new route corridor and plausible walking approaches**, including any newly visited towns. Retain query bounds, URLs, retrieval dates, response hashes, OSM IDs and relevant tags. Refresh operator records where appropriate; do not fabricate venues from geocoder results.
2. Build/reuse a pedestrian graph covering the route and approaches, preserving real connectivity, way IDs, path/road classifications, surface tags and recorded restrictions. Continue the established resolved-access assumption. Network approaches must use connected mapped ways; proximity alone is not a connection.
3. Spatially shortlist supermarkets, groceries, bakeries, other mapped food retail, cafés, restaurants, bars/pubs, fast food, drinking-water points and fuel stations. Only confirmed food/retail categories should count as food resupply.
4. Route from valid new-course attachment points to the venue vicinity and calculate each-way network distance, final entrance offset, ascent and outward walking time. Recompute `km`, `anchor_index`, `air_m`, `network_oneway_m`, `entrance_snap_m`, `walk_oneway_m`, `detour_minutes_oneway` and `detour_coords` for every retained venue. Old values are invalid even if the venue itself is unchanged.
5. The original extraction used a 650 m spatial shortlist, network walks up to 1,500 m, entrance offsets up to 100 m and total walking distance up to 1,600 m. These are extraction choices, not proof that no other services exist. If changed, record the new parameters and align UI limits/tests. Preserve the 500 m leg-icon threshold and the separately documented food-gap threshold unless deliberately changing product requirements.
6. Estimate outward time consistently with the current dataset: walking at 3 km/h plus an ascent allowance of 600 vertical m/h. Include the entrance-offset estimate in total distance/time and label it honestly. Store mapped approach geometry separately from any unsurveyed entrance offset; do not draw that offset as a verified trail.
7. Re-evaluate repeated course passes: a venue can be geographically near several widely separated kilometres. Review the chosen attachment with route order and usable approaches. The current POI schema represents one attachment per record; if multiple resupply opportunities must be represented, add an explicit occurrence model/stable occurrence IDs and adapt consumers/tests rather than silently treating the first pass as the only one.
8. Reapply checked operator schedules, contacts and source decisions by established venue identity. Deduplicate nodes/polygons and owner records carefully; distinguish multiple stores of the same brand. Recheck one-off/seasonal/holiday caveats without converting unknown hours to open.
9. Sort new POIs by course km and walking distance. Rebuild leg icon counts, passed-stop labels, map approaches, search context and food gaps from this new list. Test sections with no stops, newly added stops and endpoint stops. Keep checkpoint food separate unless supported by organiser evidence.
10. Recalculate opening status at new pace-based arrival times, including overnight and Sunday arrivals. Do not carry old open/closed results into the new route. Review increased food/water gaps before release.

### 7.4 Recalculate weather along the replacement

1. Ensure `routePoint()` now interpolates the replacement `route`, `route_km` and `profile`, and uses the rebuilt anchors/legs for place labels. Recalculate pacing from the new ascent and distance; do not reuse old projected hourly coordinates.
2. Generate a fresh outlook with `createPlan()` from the runner's validated new progress/time anchor. Verify 12/24 h positions and heights at coast, inland slopes, high ground, overnight transitions and the finish.
3. Request fresh forecast data for the new hourly latitude/longitude/elevation sequence. Open-Meteo supplied elevation must come from the new profile. Preserve units, date limits, partial coverage handling and the corrected wind-arrow convention.
4. Invalidate old route forecasts and embedded `savedWeatherData`. The existing cache checks `routeSha256` against `gpx_sha256`, so a changed GPX hash rejects the previous route's cache. If derived elevations, race date or projection logic change while GPX bytes remain identical, extend/bump cache identity or clear the affected cache; the GPX hash alone does not detect those changes.
5. Verify that old saved weather cannot appear as an outlook for the new route. When offline without a matching forecast, show unavailable/connect-once status. Never relabel old-route forecasts as new-route data.

### 7.5 Update Trail Vision and location matching

1. Rebuild the embedded canonical GPX and aligned `getAxis()` input (`DATA.track_km` converted to metres; `route_km` remains a compatibility fallback). Verify the preview parser consumes exactly the corresponding sequence of points. The downloaded GPX, map route, preview and progress HUD must agree on route identity and kilometre positions.
2. Use the replacement GPX elevations for the preview. Confirm its local filtering, ascent/descent/net change, significant climbs, true-scale rendering and optional exaggeration. A flat fallback is valid only with its missing/unreliable-height warning.
3. Reset stale preview routes, prior matches, hints and windows when the route revision changes. The current deployed route is loaded with the page; a full reload acquires the new embedded GPX. If implementing hot replacement, dispose/recreate cached Trail Vision state and rebind the shared tracker explicitly.
4. Exercise new sharp turns, switchbacks, overlapping passes, backtracking and the approach to the finish. Confirm GPS projection picks the intended pass and does not jump between nearby parts. Show uncertainty instead of snapping to a convenient far-away course kilometre.
5. In simulation and sensor tests, rotate heading/pitch while standing at one location: geometry must remain geographically fixed. Recheck portrait/landscape, manual/follow modes, markers, local-window limits and resource cleanup.
6. The preview-only file picker is not this update mechanism. Loading the replacement there does not update main-map matching, POIs, weather or the public GPX.

### 7.6 Migrate saved progress and refresh all release metadata

Plan state now includes `routeSha256`. A different or missing route identity resets progress, elapsed anchor and extra delay, retains pace/map/view preferences, and displays an explanation. Same-route progress survives reload and portable HTML saves. Previously the plan stored kilometres without route identity. Clamping an old kilometre to a new route length does **not** map the runner to the new course. Maintain this explicit route-identity migration on every replacement: retain compatible pacing and street-map preferences and reset or geographically rematch progress/time with a visible explanation. An unchanged section before a late-course correction may permit a documented mapping, but never assume equal kilometres represent equal positions. Include embedded `savedPlanData` in this review.

Update `gpx_sha256` only after derived data has been regenerated. Update `based_on`, `researched`, sources/hashes/decisions, profile method, count references and route documentation. If the event date/time or island coverage changes, update race metadata, daylight data, explicit start-time copy and relevant timezone/opening-hours assumptions. Keep the original source and new validation evidence attributable.

### 7.7 Build, verify and publish the route revision together

```sh
# Install development-only preprocessing dependencies.
python3 -m pip install -r requirements-route-update.txt
# Review both root GPXs, PDF transcription and graph/source coverage first.
python3 scripts/update_official_route.py
python3 tests/test_official_data.py
python3 scripts/build.py
npm test
python3 -m http.server 8787 --bind 127.0.0.1
```

With the localhost server running, run the browser commands in Section 8 in another terminal. The Python browser suites require Playwright and its Chromium/WebKit binaries/dependencies; they are development tools, not app runtime dependencies.

Review `index.html`, `sw.js`, the source data, sources and tests as one release. Verify the downloaded GPX is byte-identical to the new canonical GPX. Update downloadable HTML/archive copies wherever distributed, and make it clear older saved HTML files remain the old route until replaced.

Commit and push the coherent revision to this repository's `main` branch when authorized, verify GitHub Pages deployment succeeds, and check the served build matches the tested build. Test online refresh followed by offline reload with the updated service-worker cache. Include an existing-browser-storage upgrade test, not only a clean browser test. If generation inputs or continuity evidence are missing, stop and report the exact blocker; do not publish a checksum-only replacement.

## 8. Validation and acceptance

For an actual route update or functional change, use the relevant suites; for documentation-only changes, verify documentation paths, commands and factual accuracy without rerunning unrelated app tests.

```sh
npm run build
npm test
# In another terminal, with localhost:8787 serving this repository:
python3 tests/browser_test.py
python3 tests/mobile_controls_test.py --browsers chromium webkit
python3 tests/geolocation_browser_test.py
python3 tests/progress_sync_browser_test.py
python3 tests/legs_browser_test.py
python3 tests/weather_browser_test.py
python3 tests/vision_browser_test.py
python3 tests/offline_browser_test.py
python3 tests/install_browser_test.py
python3 tests/official_route_browser_test.py
python3 tests/test_official_data.py
```

Existing suites include route-specific counts, town names, fixed kilometre examples and expected finish times. A new route legitimately changes some expectations: recompute them from reviewed reference data, retain independent invariants, and do not delete failing connectivity, matching or provenance checks to make a replacement pass. Keep the synthetic Trail Vision fixture strictly as test data, separate from the published race route.

A route revision is acceptable only when:

- The canonical GPX is valid, real, continuous and ordered, with usable elevation and checkpoint waypoints; every required connection is evidenced. No unreported bridge or invented off-trail shortcut is introduced.
- GPX hash, embedded/downloaded bytes, full `track_km` point order/count, display `route`/`route_km` alignment, profile endpoint and total distance reconcile. Every canonical GPX point must have the correct full-track axis correspondence.
- Checkpoints occur in the correct order and distances are measured on the replacement, with organiser target errors documented separately. Legs cover the route once, and their distance/elevation totals reconcile within documented rounding tolerances.
- Every displayed POI is reattached to the new route with source-backed position, current approach metrics and reviewed opening evidence. No old-route stop survives solely because its stale kilometre still fits the new length.
- Completion ticks, active-leg selection, endpoint POI allocation, backwards corrections, GPS/time sync and manual fallback work through the new course and finish.
- Weather requests use the replacement's projected positions and heights; old cached forecasts are rejected; 12/24 h summaries, dates, finish truncation, offline/expired states and wind directions remain correct.
- Trail Vision previews the replacement's next cumulative 500 m with real bends/elevation, fixed-world orientation, explicit sensor fallback, correct progress alignment and no segment bridging.
- Fresh and existing-storage browser sessions, portable downloads, map actions and offline reload pass. Chrome manifest validation, install-prompt acceptance/dismissal/fallback, standalone layout, offline manifest/icons, and both on/off map preference reloads pass. The feature remains readable on Android-sized screens and in WebKit emulation.
- The release notes identify route source/revision, changed distance/terrain/checkpoints/resupply, remaining uncertainty, processing methods and the published revision.

Browser simulations verify software behaviour, not physical compass/GPS accuracy, weather reliability or battery endurance. Field-check heading/tilt, screen rotation, permission denial and offline reload on Android Chrome and iPhone Safari using [the Trail Vision checklist](docs/trail-vision.md). Record untested hardware behaviour honestly.

## 9. Deliverables and maintenance priorities

The maintained deliverable is the integrated application plus its canonical GPX/data, generated HTML/service worker, source provenance, automated checks, brief user documentation and this root-level PRD. Existing reconstruction alternatives/reports remain evidence artifacts; do not imply they are hosted app features when they are not in the repository.

The preparation pipeline and source snapshots are checked in and separate from the lightweight runtime. On future replacements, refresh route-corridor graph/POI coverage, review the organiser PDF mapping and regenerate everything coherently. Source files, derived geometry, current application identity and saved-state migration must continue to agree.

Keep [README.md](README.md) as the short usage/build guide and [docs/trail-vision.md](docs/trail-vision.md) as detailed sensor/browser documentation. When product behaviour changes, update this PRD, the affected guide, and the relevant validation evidence in the same change.
