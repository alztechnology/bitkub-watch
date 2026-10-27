# AL Wolf Bitkub Watch 🐺

Small-cap tracker for Bitkub (THB pairs). Not financial advice.

- `scan.py` fetches the Bitkub public ticker and daily candles, skips large caps/stablecoins/XAUT and anything over USD 500M market cap (CoinGecko, cached daily), and writes `data.json`.
- `.github/workflows/scan.yml` runs it every 15 minutes and commits `data.json` back.
- `index.html` is a static page (GitHub Pages) that loads `data.json`, reloads every 5 min and keeps "Our Coins" in your browser's localStorage (export/import JSON for backup).

Flags: **Volume building** (24h THB volume ≥ 1.5x the 7-day average, volume ≥ ฿100k, 24h ≤ +25%, 7d ≤ +50%), **Pumped already** (24h > +25% or 7d > +50%), **Thin volume** (< ฿100k/24h). Bad candle volume shows as n/a.

No login, wallet, trading or secrets. Run locally: `python3 scan.py`.
