# Ron_Market Scanner

Automated Smart Money Concepts (SMC) market scanner for Forex and indices.
Sends entry alerts with full narrative context to Telegram.

## Strategy

**Timeframes**
- HTF: 5-minute (bias & structure)
- LTF: 1-minute (entry detection)

**HTF Bias (structure.py)**
- Detects proper swing highs/lows (2-candle lookback each side)
- Counts HH/HL or LL/LH series for trend strength
- Caches range until a new BOS occurs (saves API calls)

**LTF Entry — Inducement + Liquidity Sweep (entry.py)**
1. Initial bullish displacement detected
2. First pullback attracts early buyers → reaction level forms
3. Liquidity sweep takes out early buyers' stops (below reaction low)
4. Recovery impulse — short bearish pullback traps sellers (inducement zone)
5. Price continues up, leaving zone behind
6. Price retests inducement zone → ENTRY at top of zone
7. SL below zone (or HTF range low if nearby)
8. TP1 = wick highs of the candles that started the pullback
9. TP2 = HTF range high + 5% buffer

Bearish case is the exact mirror.

**Session filter**: London (07–11 UTC) and New York (12–16 UTC) only.

## File Structure

| File | Purpose |
|---|---|
| `main.py` | Main scan loop |
| `config.py` | All settings + env vars |
| `data.py` | TwelveData API fetcher (rate-limited) |
| `structure.py` | HTF swing detection, bias, BOS |
| `entry.py` | LTF inducement entry logic |
| `sessions.py` | Session filter |
| `state.py` | Per-symbol cached state |
| `notifier.py` | All Telegram messaging |

## Required Environment Variables / Secrets

| Key | Description |
|---|---|
| `TWELVEDATA_API_KEY` | TwelveData API key (required for data) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Chat/channel ID for alerts |

## Running

```bash
python main.py
```
