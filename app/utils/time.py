from datetime import datetime, timezone

def utc_now() -> datetime:
    """
    返回 timezone-aware 的 UTC 时间
    """
    return datetime.now(timezone.utc)
