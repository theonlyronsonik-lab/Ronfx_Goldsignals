import time
import requests
import pandas as pd
from config import TWELVEDATA_API_KEY

_LAST_CALL = 0
_MIN_INTERVAL = 10   # seconds between requests (free plan ≈ 8/min)


def get_candles(symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
    """
    Fetch OHLC candles from TwelveData.
    Returns a chronological DataFrame or empty DataFrame on failure.
    Automatically respects rate limits.
    """
    global _LAST_CALL

    if not TWELVEDATA_API_KEY:
        print("⚠️  TWELVEDATA_API_KEY not set — cannot fetch data.")
        return pd.DataFrame()

    elapsed = time.time() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    params = {
        "symbol":     symbol,
        "interval":   timeframe,
        "outputsize": limit,
        "apikey":     TWELVEDATA_API_KEY,
        "format":     "JSON",
    }

    try:
        r = requests.get(
            "https://api.twelvedata.com/time_series",
            params=params,
            timeout=15,
        )
        _LAST_CALL = time.time()
        data = r.json()

        if data.get("status") == "error":
            code = data.get("code")
            if code == 429:
                print("⚠️  Rate limit hit — sleeping 60 s...")
                time.sleep(60)
            else:
                print(f"TwelveData error [{symbol} {timeframe}]: {data.get('message')}")
            return pd.DataFrame()

        values = data.get("values")
        if not values:
            print(f"No values returned for {symbol} ({timeframe})")
            return pd.DataFrame()

        df = pd.DataFrame(values)
        df = df.iloc[::-1].reset_index(drop=True)   # oldest → newest
        for col in ("open", "high", "low", "close"):
            df[col] = df[col].astype(float)
        return df

    except Exception as exc:
        print(f"Fetch error [{symbol} {timeframe}]: {exc}")
        return pd.DataFrame()
