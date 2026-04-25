class BotState:
    """Holds cached HTF structure and per-symbol trade state."""

    def __init__(self):
        # HTF structure (updated on BOS only)
        self.htf_bias         = None    # "BULLISH" | "BEARISH" | "RANGE"
        self.htf_series_count = 0       # how many HH/HL or LL/LH in a row
        self.htf_range_high   = None    # top of current HTF leg
        self.htf_range_low    = None    # bottom of current HTF leg

        # HTF inducement gate — updated every scan cycle.
        # htf_inducement holds the most recent complete HTF inducement zone as a
        # tuple of (zone_high, zone_low, sweep_price, narrative), or None when no
        # complete zone has been detected yet.
        # htf_inducement_complete is True only when htf_inducement is not None,
        # meaning the full HTF sequence (displacement → sweep → recovery →
        # inducement candle → continuation) has finished forming.  LTF entries
        # are only considered when this flag is True.
        self.htf_inducement          = None   # (zone_high, zone_low, sweep_price, narrative) | None
        self.htf_inducement_complete = False  # True when HTF zone is fully formed
        self.htf_inducement_timestamp = None  # datetime (UTC) when HTF zone was first detected

        # LTF setup tracking — scanned 24/7, stored here until signal gate opens.
        # ltf_setup holds the most recent qualifying LTF entry setup as a tuple of
        # (entry, sl, tp1, tp2, narrative, sweep_price), or None when no setup has
        # been found yet within the current HTF structure cycle.
        self.ltf_setup           = None   # (entry, sl, tp1, tp2, narrative, sweep_price) | None
        self.ltf_setup_timestamp = None   # datetime (UTC) when LTF setup was first detected

        # Correlation flag — True when the LTF entry price sits inside (or very
        # close to) the HTF inducement zone, confirming both structures align.
        self.setup_correlation_valid = False

        # Entry deduplication — reset only when a new HTF structure break occurs.
        # Stores the (entry_price, sl_price) of the last alerted LTF setup so that
        # the same setup is never alerted twice within the same HTF structure cycle.
        # Set to None on BOS so the next qualifying setup fires a fresh alert.
        self.last_alerted_setup = None  # (entry_price, sl_price) | None


def create_states(symbols):
    return {s: BotState() for s in symbols}
