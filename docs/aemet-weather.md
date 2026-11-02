# AEMET integration

The 12/24-hour **Weather ahead** panel prefers numerical AEMET municipal forecasts where the projected runner position has a reasonably nearby town forecast at a similar altitude. Each forecast card identifies its provider. Open-Meteo remains the explicit fallback for remote/high sections, dates outside AEMET's short horizon, stale snapshots and unavailable feeds. This is an additional source, not a demonstrated improvement in forecast accuracy.

## Sources evaluated

- [AEMET's numerical hourly XML](https://www.aemet.es/xml/municipios_h/localidad_h_35025.xml), linked from its [official municipal forecast pages](https://www.aemet.es/es/eltiempo/prediccion/municipios/). These public feeds require no API key. All 21 Gran Canaria municipalities were downloaded successfully. Published capital coordinates and altitudes are versioned in `data/weather/aemet-towns.json`, with page URLs, retrieval date and source hashes. These are town forecast locations, not observation stations.
- [AEMET's HARMONIE-AROME Canarias download](https://www.aemet.es/es/api-eltiempo/modelos/download/harmonie/CAN). The live 8.6 MB archive contained 440 GeoTIFF/GeoJSON map members. Rasters were JPEG-compressed RGBA pictures with colour bands: temperature commonly 2 °C bands and wind speed 10 km/h bands. Direction data was much coarser, at 0.20 degrees. These are not the raw model's continuous numerical fields. The implementation does **not** convert map colours into apparently precise point forecasts. [AEMET documents these formats and resolutions](https://www.aemet.es/es/eltiempo/prediccion/modelosnumericos/harmonie_arome/ayuda).
- [OpenData REST API](https://opendata.aemet.es/dist/): also provides municipal numerical forecasts but requires an API key. We use the official public numerical XML instead, so no key, credential sharing or new hosting account is needed.

The live, same-time comparison of 11 official-course positions is recorded in [aemet-source-comparison.json](aemet-source-comparison.json). Nine positions had eligible town forecasts, while Parque Sur and the highest GPX profile point did not. A town-based swap for the entire island would therefore introduce obvious altitude or distance mismatches. Both providers differed at several positions. This was a **forecast-to-forecast comparison without observations**, and cannot establish which provider was correct.

## Forecast selection and interpretation

The existing pace/progress calculation still produces the same 25 hourly GPX positions, or a shorter path ending exactly at the finish. At each position:

1. Require an AEMET town within **8 km**, within **250 m elevation**, downloaded within **6 hours**, with time coverage and a valid temperature. These thresholds are **heuristics, not calibrated accuracy bounds**. They cannot account for windward/leeward aspect or every mountain microclimate.
2. Rank eligible towns by `horizontal_distance / 2000 + absolute_height_difference / 100`, then deterministic municipality ID. Try the next eligible town if the first has no forecast at the requested time.
3. Use the selected town's forecast as published, without a fabricated altitude correction. The card gives town altitude, distance from the GPX position, signed route-vs-town height difference, and original download time. It must never label these values as forecasts at the exact GPX height.
4. Use Open-Meteo's existing route-position request, with GPX elevation supplied, for uncovered positions. Do not substitute another date or fill individual AEMET fields from another provider. Missing fields stay unavailable. If every projected position is covered by AEMET, skip Open-Meteo entirely.

Temperatures and mean wind speed interpolate between adjacent hours only; no interpolation across missing hours or beyond the horizon. Weather codes/direction use the nearest supported sample. Spanish `O/NO/SO` wind directions convert to `W/NW/SW` source bearings; the arrow remains the direction the air travels, `(source + 180) % 360`. Gusts are not treated as mean wind.

AEMET instantaneous timestamps use the capital's local timezone, `Atlantic/Canary`; multi-hour probability intervals use UTC, following [AEMET's interpretation notes](https://www.aemet.es/es/eltiempo/prediccion/municipios/). Six-hour probability remains a **six-hour probability**, including when displayed alongside hourly Open-Meteo values. No division into invented hourly chances. The summary gives the largest listed probability and names the differing periods; it is not the probability for the entire route outlook. AEMET's rain/gust XML timestamps describe the following hour; `aemet.js` aligns rain to the existing end-of-hour moving-route sum. Rain totals remain approximate, particularly for fractional hours and a moving runner.

Original AEMET `elaborado` is retained as `issuedLocal` without guessing an undocumented timestamp offset. Downloads carry an explicit UTC epoch. The app's fetch time records when the runner's trajectory was refreshed; each AEMET card retains the weather download time so reprojection never makes an old source appear newly downloaded.

AEMET's hourly horizon is approximately 48 hours **from a fixed model run, not from the current clock time**. A fresh download can still stop before a requested time less than 48 hours away. The panel now reports the actual end of eligible hourly temperature coverage and the requested outlook start, and distinguishes coverage limits from stale data, feed failure, missing values or location/elevation mismatch. Existing v3 snapshots without this metadata receive one normal online refresh; their original offline forecasts remain usable.

On 2 November at 10:53 UTC, the official Gáldar XML and the scheduled cache matched byte-for-byte: issue `2026-11-02T09:19:07`, downloaded `2026-11-02T09:35:32.915Z`, hourly temperatures ending **4 November 05:00 GMT**, before the **09:00 start**. The same source snapshot is retained in `tests/fixtures/aemet-galdar-20261102.json`, including its official source hash. The fallback was correct; no AEMET values are extrapolated to 09:00. Regression tests verify the explanation and the switch to AEMET after a simulated next run genuinely covers the start.

 On 1 November it does not yet cover the 4 November start. The app therefore shows explicitly labelled Open-Meteo forecasts until AEMET covers the requested race hours. During the race the moving 12/24-hour outlook can select AEMET as data becomes available. AEMET municipal forecasts are automatically postprocessed numerical forecasts; they are not a bespoke forecaster-reviewed mountain bulletin.

## Island outlook over the next 72 hours

The same scheduled feed now also downloads four dated daily text bulletins overlapping the next 72 hours from `https://www.aemet.es/es/api-eltiempo/prediccion/{date}/CAN/9/6590`, the public endpoint used by AEMET's own [Gran Canaria general forecast](https://www.aemet.es/es/eltiempo/prediccion/espana?p=353). The endpoint can return **Gran Canaria** (root ID `90`) for the near term and **Canary Islands** (`coo`) for later dates. Preserve that scope; never label the regional bulletin as island-specific. Reject national (`esp1`) fallback responses, wrong validity dates and empty text.

The application shows the original **Spanish** forecast paragraphs and any significant-phenomena text under dated, region-labelled headings. No translation service, generated trend, invented probability or weather rating is added. Bulletin issue times and links are folded below the readable overview. Four calendar days may overlap a rolling 72-hour window; full daily text can also describe parts of the boundary days outside that exact interval. The heading therefore explains that these are daily bulletins overlapping the window. Missing days produce a visible partial-coverage label.

This outlook is independent of route progress and of the 12/24-hour selector. It remains useful when the route forecast is unavailable or the runner has finished. Separate local storage `canarias360-island-outlook-v1` and portable HTML `savedOutlookData` preserve original source dates and age. Expired bulletins, invalid/future download times and downloads over 24 hours old are excluded; offline data is labelled. A download over 12 hours old is flagged in its source information. Failed server downloads retain the old bulletin and its original fetch time. Changing to a different island requires replacing this source and invalidating the separate regional cache.

Actual source snapshots are in `tests/fixtures/aemet-bulletin-20261102.xml`, `aemet-bulletin-20261104.xml` and `aemet-island-outlook-20261102.json`. Tests cover scope fallbacks, dates, missing days, escaping, stale/expired text, 72-hour coverage, mobile layout and offline HTML. The existing workflow's parser-test step includes these checks without extra dependencies.

## Scheduled cache and offline use

`.github/workflows/aemet-weather.yml` runs at minute 17 of every second UTC hour and on relevant script/metadata changes. GitHub schedules are best-effort and can be delayed. It runs parser tests, restores the previous cache, downloads the 21 feeds with four bounded workers and retries, then publishes compact JSON to the **`weather-data` branch**, at `aemet.json`.

The application reads `https://raw.githubusercontent.com/bigreddog/360-26/weather-data/aemet.json` with CORS, avoiding AEMET's absent browser CORS headers and avoiding unnecessary full-site rebuilds or Pages deployments every two hours. The public data contains no runner position or plan. This feed is generic to the island, so it does not require a GPX hash; the resulting runner-specific forecast cache does.

The workflow uses only GitHub's built-in token with `contents: write`. No AEMET key or paid service. Fetch failures retain each affected town's previous snapshot **with its old fetch timestamp**; all-feed failure leaves the last published cache untouched and fails the workflow. The client rejects stale AEMET on fresh online projection, and falls back visibly. Browser **Refresh** checks the published cache, not a new model run. It cannot force AEMET to issue a new forecast. Use the workflow's **Run workflow** action to fetch again on the server.

Browser requests for this cache are throttled to ten minutes except manual Refresh. Existing 30-minute forecast refresh, visibility gating, request timeouts and failure backoff remain. Switching 12/24 hours makes no request. The app needs no new runtime dependency.

The route-specific browser cache is now `canarias360-weather-v3` / schema 3, to preserve source/period information and reject older snapshots. Same-route pace/progress/map preferences remain. **Save offline HTML** embeds the selected forecast and provider metadata. Offline data retains original times and positions; expired forecast windows suppress numerical summaries. A fresh forecast still requires connectivity.

## Maintenance and verification

```sh
python3 scripts/update_aemet_weather.py
python3 -m unittest discover -s tests -p test_aemet_weather.py
node tests/aemet.test.js
npm test
npm run build
# With the existing Playwright environment and local server:
python3 tests/aemet_browser_test.py
python3 tests/weather_browser_test.py
```

To publish a snapshot manually, run `scripts/publish_aemet_weather.py` using the configured GitHub credential through `GH_TOKEN`; never add a token or key to source or public JSON. Local `data/weather/aemet.json` is ignored; the production snapshot lives on `weather-data`.

For a replacement GPX, recalculate its route positions/elevations, invalidate the route-specific v3 cache and re-evaluate the **spatial/elevation eligibility at every forecast hour**. Do not carry over old town assignments. If the route leaves Gran Canaria, first replace the capital metadata and timezones with verified local sources, review the selection limits, and update the scheduled feed. Keep `PRD.md` current.

Chromium and WebKit automated tests cover both sources, mixed probability periods, source labels, 320/390/844 px layouts, wind arrows, stale/failed feeds, full-AEMET request suppression, partial fallback failure, original source attribution offline, and hidden-tab polling. These are software tests with mocked forecast values, not meteorological accuracy validation or physical phone tests.
