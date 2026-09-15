# WrappedNow

WrappedNow is a local-first Spotify library analysis and organization workbench.
It is designed primarily for one owner using Spotify Development Mode, either
on a local PC or a private home server.

The current application can select owned playlists and Liked Songs, normalize
their metadata, persist it in SQLite, and visualize library relationships and
statistics. See [TODO.md](TODO.md) for the product direction and roadmap.

## Local development

1. Create a Spotify Development Mode app and add this redirect URI:

   ```text
   http://127.0.0.1:8000/callback
   ```

2. Create `.env` in the repository root:

   ```text
   APP_ENV=development
   SPOTIFY_CLIENT_ID=...
   SPOTIFY_CLIENT_SECRET=...
   SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/callback
   SESSION_SECRET_KEY=replace-with-a-long-random-value
   # Optional; defaults to data/wrappednow.sqlite3
   MUSIC_DB_PATH=data/wrappednow.sqlite3
   ```

3. Install and run:

   ```powershell
   py -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn web.app:app --reload --host 127.0.0.1 --port 8000
   ```

4. Open `http://127.0.0.1:8000`.

Do not use `localhost` for Spotify OAuth. Spotify permits the loopback IP for
local HTTP development, while a deployed callback must use HTTPS.

## Home server direction

The eventual server process will still be an ASGI server running
`web.app:app`. Before exposing it beyond a trusted LAN or VPN:

- set `APP_ENV=production`;
- use a strong `SESSION_SECRET_KEY`;
- put it behind an HTTPS reverse proxy;
- configure the exact HTTPS `/callback` URL in Spotify's dashboard;
- move OAuth tokens to server-side storage;
- add an owner authentication layer; and
- arrange automated backups of the SQLite database.

Docker/Compose and reverse-proxy configuration are intentionally deferred until
the local synchronization and catalog model settle.
