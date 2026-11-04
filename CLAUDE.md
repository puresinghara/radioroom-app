# Radio Room: notes for Claude

Android internet-radio app (Capacitor 6, appId `com.radioroom.app`). The user speaks Thai: reply in Thai. App UI text is
English; only station / episode content is Thai. Test device: Xiaomi 17 Ultra (HyperOS), plus Android Auto / Bluetooth in a car.

## Where things live (read only the part you need; the big files are expensive)
- `www/index.html` (~240 KB, single file: CSS + JS). Station list is `STATIONS` near the top. Logos are files in
  `www/img/stations|channels`, fonts in `www/fonts` (not base64).
- **All Android native code is NOT in the repo.** `.github/workflows/main.yml` (2,200+ lines) generates it with heredocs
  (`cat << 'EOF' > android/app/src/main/...`) after `npx cap add android`: MainActivity (+ `AndroidBridge` JS interface:
  updateMedia, stopMedia, updateRecents, updateStations, getTsfJazzNowPlaying), MediaNotificationService
  (MediaBrowserServiceCompat for Android Auto, audio focus, call detection), MediaActionReceiver,
  BackgroundMediaWebView, RadioRoomWidgetProvider, AppImageLoader, widget layouts/drawables.
  Find a block with Grep for `cat << 'EOF' >`; heredoc bodies are indented 10 spaces and each ends with a line that is
  exactly 10 spaces + `EOF`. Edit by line range, never read the whole file.
- YouTube episodes: `scripts/update_ghost_episodes.py` -> `ghost_episodes.json` (repo root, **this is what the app
  fetches** from raw.githubusercontent) and `www/ghost_episodes.json` (bundled copy). `update_episodes.yml` runs it
  every 6 h and commits with `[skip ci]`. Episodes carry `ts` (ISO publish time) and `views`; the app formats dates.

## Hard-won rules
- Widgets (RemoteViews) only allow FrameLayout/LinearLayout/RelativeLayout/GridLayout + ImageView/TextView/Button etc.
  A plain `<View>` makes the launcher show "Can't load widget".
- The WebView (Chromium) requests its own audio focus. Never stop playback on a permanent `AUDIOFOCUS_LOSS` unless a call
  is detected (`isInCallMode()`); otherwise music plays for a second and stops.
- tsfjazz.com sends no CORS headers: fetch its now-playing through native HTTP (CapacitorHttp / AndroidBridge).
- Native code reads bundled logos through `AppImageLoader` (assets/public/...). Widget bitmaps must stay small.
- Android Auto draws its own UI; we only supply the browse tree, titles and 96 px icons (`files/aa_icons2`).
- Design: glass (translucent cards, white play button). Home backdrop is a fixed green glow (not station colour).
  Widget background is ONE tint colour taken from the cover, never the cover pixels (low-res art looks blocky).
- Opening `index.html` as a file in the browser shows broken images; serve `www/` over http (a PowerShell HttpListener
  script works; Python is also installed). TSF Jazz CORS errors in a desktop browser are expected.

## Build and push (Windows, PowerShell)
- This folder is **not** a git repo. Source of truth is GitHub `puresinghara/radioroom-app` (public, branch `main`).
  Clone it into a scratch folder, copy changed files in, commit, push.
- Git: `D:\Users\chumpon_s\AppData\Local\Programs\Git\cmd\git.exe` (not on PATH). Python 3.12:
  `D:\Users\chumpon_s\AppData\Local\Programs\Python\Python312\python.exe`. The user's GitHub login is stored in Git
  Credential Manager; push non-interactively with `$env:GIT_TERMINAL_PROMPT = "0"`. If it asks for a login the user must
  sign in themselves in their own PowerShell.
- Every push to `main` builds the APK (workflow "Build Android APK", about 3 min). Watch it with the unauthenticated
  GitHub API (`/actions/runs?head_sha=...`). The APK is the artifact `RadioRoom-Release-APK`; the user downloads it from
  the run page (needs their login). Java is only compiled in CI, so a green build is the compile check.
- Add `[skip ci]` to commits that should not trigger a build (docs, data).

## How the user likes to work
- Design changes: show a mockup first, build only after they approve ("ขอผมดูก่อน"). Investigate bugs before changing code.
- They care about token use: use Sonnet for routine edits, avoid re-reading big files, send few screenshots.
- After a UI change, tell them to remove and re-add the widget, and what to check on the phone.
