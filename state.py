class BotState:
    """Holds cached HTF structure and per-symbol trade state."""

    def __init__(self):
        # HTF structure (updated on BOS only)
        self.htf_bias         = None    # "BULLISH" | "BEARISH" | "RANGE"
        self.htf_series_count = 0       # how many HH/HL or LL/LH in a row
        self.htf_range_high   = None    # top of current HTF leg
        self.htf_range_low    = None    # bottom of current HTF leg

        # Trade gate — reset when new BOS forms
        self.trade_taken      = False
        self.last_entry_zone  = None    # (zone_low, zone_high) last alerted zone


def create_states(symbols):
    return {s: BotState() for s in symbols}
