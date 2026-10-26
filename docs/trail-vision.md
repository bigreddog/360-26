# Trail Vision

Open **Map → Trail Vision** in the [hosted roadbook](https://bigreddog.github.io/360-26/). Hold the phone upright with the screen facing you and the back pointing towards the trail. Turn and tilt the phone to look around. This is a virtual GPX preview: it uses neither the camera nor video.

The default is a 500 m preview at true vertical scale, driven by compass orientation. The cyan ribbon is geographically anchored; sensor changes rotate the virtual camera, not the route. The HUD shows route kilometre, heading/reference, sensor quality, GPS accuracy, look-ahead, ascent, descent and net elevation change. Markers occur every 100 m; overlapping labels are suppressed for legibility, while their dots remain visible. The reference grid is a flat plane, not terrain.

## Controls

- **Recenter** clears offsets introduced by dragging the view. It does not set north or rotate the GPX to face the phone.
- **Compass view** uses the phone's heading and tilt. Roll is transformed for the current screen orientation, then damped and capped at 8° to keep the horizon comfortable.
- **Manual heading** and **Follow route** are explicit alternatives. Their camera headings are labelled as view headings; they are never passed off as sensor readings. Use the tilt slider in these modes.
- **Settings & help** contains 100 / 250 / 500 / 1,000 m look-ahead, 1× / 1.5× / 2× / 3× vertical scale, an approximate route-kilometre hint, simulation and a local GPX picker.
- **Set hint** helps identify a repeated pass at a crossing. It does not force a GPS position off the route.
- **Preview without GPS** starts clearly labelled simulation at the last planning kilometre. Simulation offers position, heading and pitch controls and uses the same renderer and orientation mathematics.
- **Exit** or Escape closes the view and releases its resources.

Preferences use the roadbook's existing local plan storage and portable HTML save. Simulation and sensor permissions are not restored automatically. An uploaded GPX is for this preview only and stays in memory for the browser session; it does not replace the race map, resupply data or GPX download.

## Permissions and north reference

GPS and orientation require a secure context: HTTPS or localhost. Opening Trail Vision requests location and, where required, device orientation permission in the initiating tap. On iOS, motion permission is also requested so rotation-rate readings can corroborate sensor quality; denial of that optional permission does not prevent compass use. Android may provide orientation events without a separate prompt. No camera permission is requested.

Browser heading references vary. iOS `webkitCompassHeading` is labelled **Magnetic north**. Android absolute orientation is labelled **North ref unverified**, because the browser does not reliably expose whether its north reference is magnetic or geographic. No declination model is bundled, and no true-north correction or accuracy claim is made. The GPX geometry uses geographic north, so magnetic/device heading errors can offset its apparent direction.

The camera looks out the back of the screen, not along the top edge of a flat phone. A phone lying face up therefore looks down. Portrait and landscape use the W3C device Z-X-Y quaternion and the screen's rotation. Quaternion interpolation smooths changes with an approximately 110 ms time constant, including crossing north and near-vertical poses.

Compass states mean:

| State | Meaning |
| --- | --- |
| Good | Several available readings appear usable; this is not a measured accuracy or a calibrated probability. |
| Uncertain | Startup, an isolated implausible jump, reported broad accuracy, or no recent update. |
| Unavailable | No absolute heading, denied/unsupported sensors, or readings absent for 30 seconds. |
| Calibration suggested | Reported poor sensor quality, or repeated abrupt heading changes contradicted by a fresh, nearly still gyroscope. |

Movement alone never triggers **Calibration suggested**. Without gyroscope corroboration or a reported accuracy/status, the app cannot establish magnetometer calibration quality. At ten seconds without a new reading, the last orientation is held with an uncertainty message; after thirty seconds it is unavailable. The browser may suspend sensors when backgrounded.

The warning is: “Compass accuracy may be low. Move away from metal objects and calibrate your phone if needed.” Help explains that figure-eight movement may help on some devices. The web app cannot calibrate the magnetometer.

## Geometry, matching and elevation

`vision-core.js` contains the reusable, dependency-free maths. `vision.js` owns the dialog, sensors, view lifecycle and Canvas renderer. `vision.css` is scoped to the fullscreen dialog. The existing builder embeds all three in `index.html` alongside Leaflet, the GPX and roadbook data.

The embedded GPX is parsed lazily with `DOMParser`. Coordinates and elevation come from its real track points. Its full `track_km` cumulative distance axis is reused to align with roadbook kilometres; the map’s simplified `route_km` array must not be passed to the full GPX parser. A custom GPX gets a cumulative haversine distance axis. Distances are horizontal track distance, not a straight-line radius or slope-adjusted distance.

Matching projects the GPS fix fractionally onto valid GPX segments. Spatial offset, the prior progress, elapsed time and accuracy constrain plausible passes in both directions, allowing backtracking. Distant progress jumps and unresolved nearby passes produce an ambiguity warning. Accuracy worse than 80 m is rejected. Off-route distance is compared with an accuracy-dependent 35–80 m threshold; fixes older than two minutes are rejected. These are heuristics, not probabilities. A bad fix leaves the preview at its last matched position, with an explicit warning.

GPX track segments are never joined. Missing coordinates split continuity; an individual point-to-point jump over 400 m is conservatively treated as an unverified sparse gap. The preview stops at that segment end and says so. A coarse GPX may therefore need denser source geometry rather than being bridged by this app.

The next route window is resampled at 5 m intervals: at most 201 points for 1 km. Latitude/longitude become local east/north/up metres around the projected position. The eye is 1.7 m above its interpolated GPX elevation. Elevation receives a short triangular filter with a 10 m radius, preserving window endpoints. Ascent/descent are calculated from that filtered preview; net change is its endpoint difference. A sustained grade of at least 6% over at least 30 m and 3 m of change is shown as an upcoming significant climb or descent. These local totals can differ from the roadbook's coarser elevation-processing method.

Missing, out-of-range or implausibly spiking elevation produces an explicitly labelled flat preview. Vertical exaggeration affects rendering only, not the eye height, horizontal distance or reported gain/loss. The race GPX uses organiser-supplied elevations; this is not a surveyed view of steps, rocks, obstacles or the actual horizon.

## Rendering, battery and offline use

There is no new third-party runtime dependency. Canvas draws a perspective-projected 3D ribbon, with near-plane polygon/line clipping and depth sorting. WebGL is unnecessary, so devices without WebGL use the same renderer. No photorealistic terrain or external imagery is fetched.

Only the local window is rendered. Animation is capped at approximately 30 fps, device pixel ratio at 1.5, and frames stop once orientation settles. Identical sensor readings do not continuously redraw. Hidden views stop animation and detach orientation listeners. Exit removes subscriptions, intervals and resize observers, cancels animation, releases the Canvas pixel buffer and stops a GPS watch started by Trail Vision. A GPS watch that the racer enabled independently remains active; it is shared, not duplicated. Route data remains in memory for reuse. Actual battery consumption has not been measured on physical phones.

The hosted app registers `sw.js`, which caches the single self-contained HTML document, including GPX and all preview code. After the first successful online load, **Downloads & tools** reports “Offline roadbook ready.” Subsequent navigations try the network for up to 3.5 seconds, then use the cached HTML. A new build installs a versioned cache; old roadbook caches are cleaned up. Business pages and online map tiles are not cached by this feature.

**Save offline HTML** remains a separate backup. Some mobile browsers restrict GPS or orientation in downloaded files, even though the preview and simulation code work there. Use the cached HTTPS app when live sensors are required. Browser storage can be cleared or evicted, so verify offline readiness before the event. Raw sensor fixes and camera data are not cached, persisted or sent to an application server. The separate raster street-map toggle still requests OSM tiles only if enabled.

## Android Chrome field check

1. Open the hosted HTTPS app online. Check **Downloads & tools** for offline readiness.
2. Enable Android Location and allow Chrome/site location. If blocked, review the site's Location and Motion sensors permissions.
3. At a known route location, open **Map → Trail Vision**. Confirm route kilometre and GPS accuracy.
4. Hold the phone upright, turn about 90° both ways, then tilt it. The geographically fixed route should move opposite the viewing turn, with real bends and climbs preserved. Try portrait and landscape.
5. Compare a recognisable trail direction with the view. Treat disagreement as a heading-quality limitation; use Manual or Follow route when necessary.
6. Close Trail Vision. If GPS was off before entry, confirm it is off again. If you enabled GPS independently, it should remain on.
7. With the page cached, turn off data/Wi-Fi and reload. Check the map and Trail Vision. GPS still requires its device/browser permission and a usable fix.

## iPhone Safari field check

1. Open the HTTPS app in Safari with Location Services available.
2. Open Trail Vision and grant the orientation/motion prompts. Location may ask separately. A denied optional motion prompt can reduce quality diagnostics without preventing heading use.
3. Confirm **Magnetic north** is labelled when the iOS heading is provided. Repeat the turn, tilt and screen-rotation checks above.
4. If permission is denied or the heading remains unavailable, explicitly choose Manual heading or Follow route; reopen/review Safari permissions to retry sensors.
5. Verify offline reload before leaving coverage. Do not assume a downloaded file has live sensor permission.

## Automated verification and limits

Run `npm run build` and `npm test`. With the repository served on localhost, run the existing browser suites plus:

```sh
python3 tests/vision_browser_test.py
python3 tests/offline_browser_test.py
```

The synthetic GPX in `tests/fixtures/trail-vision-synthetic.gpx` contains sharp turns, switchbacks, sustained ascent/descent and a close return loop. It is test data, never part of the published race route. Unit tests cover cumulative distances, interpolation, gaps, ENU coordinates, elevation, matching/backtracking, perspective, compass/screen transforms, quaternion smoothing and confidence transitions. Browser tests exercise real embedded GPX data, simulated GPS/Android/iOS events, world-fixed geometry, permission failures, quality warnings, fallback modes, preferences, cleanup, GPX imports and offline cold reload in Chromium and WebKit. Tests block external data requests, and explicitly run without WebGL.

These are browser emulation tests. Physical Android/iPhone sensor accuracy, magnetic interference, GPS performance, thermal behaviour and battery life have not been field-tested here. Trail Vision previews the official GPX; it does not establish trail access, obstacle clearance or event-course correctness.
