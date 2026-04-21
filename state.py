class BotState:
    """Holds cached HTF structure and per-symbol trade state."""

    def __init__(self):
        # HTF structure (updated on BOS only)
        self.htf_bias         = None    # "BULLISH" | "BEARISH" | "RANGE"
        self.htf_series_count = 0       # how many HH/HL or LL/LH in a row
        self.htf_range_high   = None    # top of current HTF leg
        self.htf_range_low    = None    # bottom of current HTF leg

        # Entry deduplication — reset only when a new HTF structure break occurs.
        # Stores the (entry_price, sl_price) of the last alerted LTF setup so that
        # the same setup is never alerted twice within the same HTF structure cycle.
        # Set to None on BOS so the next qualifying setup fires a fresh alert.
        self.last_alerted_setup = None  # (entry_price, sl_price) | None


def create_states(symbols):
    return {s: BotState() for s in symbols}
