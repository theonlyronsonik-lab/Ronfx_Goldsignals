from datetime import datetime, timezone


def in_trading_session():
    """
    Returns (in_session: bool, session_name: str).
    London kill zone : 07:00 – 11:00 UTC
    New York kill zone: 12:00 – 16:00 UTC
    """
    hour = datetime.now(timezone.utc).hour

    if 6 <= hour <= 11:
        return True, "London"
    if 11 <= hour <= 16:
        return True, "New York"
    return False, "Off-session"
