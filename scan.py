#!/usr/bin/env python3
"""Bitkub small-cap scanner. Writes data.json. Public market data only, no keys."""
import json, os, time, datetime as dt, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "bitkub-watch/1.0"}
EXCLUDE = set("""BTC ETH XRP SOL BNB ADA DOGE TRX LINK NEAR HYPE XLM SUI WLD PEPE UNI AAVE
LTC BCH DOT AVAX MATIC POL SHIB TON ATOM ETC XMR HBAR APT ARB OP FIL ICP INJ TAO ENA
USDT USDC DAI TUSD BUSD FDUSD USDD XAUT PAXG KUB""".split())
MCAP_MAX = 500_000_000
MIN_VOL = 100_000

def get(url, timeout=20, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(1.5 * (i + 1))

def mcaps():
    """CoinGecko market caps by symbol, cached daily to stay in free limits."""
    path = os.path.join(HERE, "mcap_cache.json")
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    try:
        c = json.load(open(path))
        if c.get("date") == today and c.get("caps"):
            return c["caps"]
    except Exception:
        c = {}
    caps = {}
    for page in (1, 2, 3, 4):
        d = get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=%d" % page)
        if not d:
            break
        for x in d:
            s = (x.get("symbol") or "").upper()
            m = x.get("market_cap") or 0
            caps[s] = max(caps.get(s, 0), m)
        time.sleep(2.5)
    if caps:
        json.dump({"date": today, "caps": caps}, open(path, "w"))
        return caps
    return c.get("caps", {})  # stale cache is better than nothing

def candles(sym, now):
    d = get("https://api.bitkub.com/tradingview/history?symbol=%s_THB&resolution=1D&from=%d&to=%d" % (sym, now - 10 * 86400, now))
    if not d or d.get("s") != "ok":
        return None
    return d

def analyse(sym, t, now):
    last = float(t.get("last") or 0)
    row = {"symbol": sym, "price": last, "chg24h": t.get("percentChange"),
           "vol24h": float(t.get("quoteVolume") or 0), "volRatio": None, "chg7d": None,
           "mcapUsd": None, "flags": []}
    d = candles(sym, now)
    if d:
        c, v, t_ = d["c"], d["v"], d["t"]
        today0 = now - now % 86400
        full = [(tt, cc, vv) for tt, cc, vv in zip(t_, c, v) if tt < today0]
        last7 = full[-7:]
        # THB volume per day approx = base volume * close; bad values -> n/a
        vols = [vv * cc for _, cc, vv in last7 if vv and vv > 0 and cc and cc > 0]
        if len(vols) >= 5:
            avg = sum(vols) / len(vols)
            if avg > 0 and avg == avg:
                row["volRatio"] = round(row["vol24h"] / avg, 2)
        if len(full) >= 7 and full[-7][1] > 0:
            # close 7 full days ago -> current price
            row["chg7d"] = round((last / full[-7][1] - 1) * 100, 2)
    return row

def flag(r):
    f = []
    ch, c7, ra, vol = r["chg24h"] or 0, r["chg7d"], r["volRatio"], r["vol24h"]
    if vol < MIN_VOL:
        f.append("Thin volume")
    if ch > 25 or (c7 is not None and c7 > 50):
        f.append("Pumped already")
    if ra is not None and ra >= 1.5 and vol >= MIN_VOL and ch <= 25 and (c7 is None or c7 <= 50):
        f.append("Volume building")
    return f

def main():
    now = int(time.time())
    tick = get("https://api.bitkub.com/api/market/ticker")
    if not tick:
        raise SystemExit("ticker failed")
    caps = mcaps()
    syms = []
    for k, t in tick.items():
        s = k.replace("THB_", "")
        if not k.startswith("THB_") or s in EXCLUDE or t.get("isFrozen"):
            continue
        if caps.get(s, 0) >= MCAP_MAX:
            continue
        syms.append((s, t))
    with ThreadPoolExecutor(max_workers=6) as ex:
        rows = list(ex.map(lambda a: analyse(a[0], a[1], now), syms))
    for r in rows:
        r["mcapUsd"] = caps.get(r["symbol"]) or None
        r["flags"] = flag(r)
    rows.sort(key=lambda r: (-(r["volRatio"] or 0)))
    # prices for every coin in ours.json, even if excluded from the scan list
    ours = {}
    try:
        for m in json.load(open(os.path.join(HERE, "ours.json"))):
            t = tick.get("THB_" + m["sym"].upper())
            if t:
                ours[m["sym"].upper()] = {"price": float(t.get("last") or 0), "chg24h": t.get("percentChange"),
                                          "vol24h": float(t.get("quoteVolume") or 0)}
    except Exception as e:
        print("ours.json skipped:", e)
    out = {"updatedUtc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "count": len(rows), "coins": rows, "ours": ours}
    json.dump(out, open(os.path.join(HERE, "data.json"), "w"), separators=(",", ":"))
    print("wrote", len(rows), "coins;", sum("Volume building" in r["flags"] for r in rows), "volume building")

if __name__ == "__main__":
    main()
