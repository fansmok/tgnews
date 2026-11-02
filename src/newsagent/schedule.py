from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from newsagent.runtime import parse_iso

MSK = ZoneInfo("Europe/Moscow")
SLOT = timedelta(minutes=30)
AD_HOLD = timedelta(hours=1)
BROADCAST_HOLD = timedelta(minutes=15)
WINDOW_START = time(10, 0)
REGULAR_LEAD = timedelta(minutes=45)
OVERWRITE_LEAD = timedelta(minutes=70)
BROADCAST_LEAD = timedelta(minutes=25)
LATE_GRACE = timedelta(seconds=180)
OVERWRITE_LATE = timedelta(minutes=20)
SCHEDULE_BUFFER = timedelta(seconds=20)
DAILY_REGULAR_POSTS = 6
# Окна дня (не фиксированные часы): в каждом окне один пост в «случайную» минуту (стабильно на дату).
POST_BANDS: tuple[tuple[int, int, int, int], ...] = (
    (10, 0, 11, 45),
    (11, 45, 13, 30),
    (13, 30, 15, 15),
    (15, 15, 17, 45),
    (17, 45, 20, 15),
    (20, 15, 22, 30),
)


def midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=MSK)


def _day_rng(day: date) -> random.Random:
    return random.Random(day.toordinal() ^ 0xF00BA11)


def _band_bounds(day: date, band: tuple[int, int, int, int]) -> tuple[datetime, datetime]:
    sh, sm, eh, em = band
    start = datetime(day.year, day.month, day.day, sh, sm, tzinfo=MSK)
    end = datetime(day.year, day.month, day.day, eh, em, tzinfo=MSK)
    return start, end


def baseline_slots(day: date) -> list[datetime]:
    rng = _day_rng(day)
    moments: list[datetime] = []
    for band in POST_BANDS:
        start, end = _band_bounds(day, band)
        span_minutes = max(0, int((end - start).total_seconds() // 60))
        if span_minutes <= 0:
            continue
        offset = (rng.randint(0, span_minutes) // 5) * 5
        moments.append(start + timedelta(minutes=offset))
    return sorted(moments)


def regular_slot_window(day: date, moment: datetime) -> tuple[datetime, datetime] | None:
    moment = moment.astimezone(MSK)
    for band in POST_BANDS:
        start, end = _band_bounds(day, band)
        if start <= moment <= end:
            return start - REGULAR_LEAD, end + LATE_GRACE
    return None


def regular_slots(day: date) -> list[datetime]:
    return baseline_slots(day)


def _normalize_ads(ads: list) -> list[dict]:
    normalized: list[dict] = []
    for item in ads:
        if isinstance(item, dict):
            dt = item["time"]
            if isinstance(dt, str):
                dt = parse_iso(dt)
            kind = item.get("kind", "regular")
        elif isinstance(item, str):
            dt = parse_iso(item)
            kind = "regular"
        elif isinstance(item, datetime):
            dt = item
            kind = getattr(item, "ad_kind", "regular")
        else:
            continue
        normalized.append({"time": dt.astimezone(MSK), "kind": kind})
    normalized.sort(key=lambda x: x["time"])
    return normalized


def blackout_intervals(ads: list) -> list[tuple[datetime, datetime]]:
    norm = _normalize_ads(ads)
    intervals: list[tuple[datetime, datetime]] = []
    for ad in norm:
        t = ad["time"]
        dur = BROADCAST_HOLD if ad["kind"] == "broadcast" else AD_HOLD
        intervals.append((t, t + dur))
    return intervals


def in_blackout(moment: datetime, ads: list) -> bool:
    moment = moment.astimezone(MSK)
    return any(start <= moment < end for start, end in blackout_intervals(ads))


def overwrite_slots(ad: dict) -> list[tuple[datetime, str]]:
    t = ad["time"]
    if ad["kind"] == "broadcast":
        return [
            (t + timedelta(minutes=15), "broadcast_overwrite"),
            (t + timedelta(minutes=45), "broadcast_overwrite"),
            (t + timedelta(minutes=90), "broadcast_overwrite"),
        ]
    return [
        (t + timedelta(hours=1), "ad_overwrite"),
        (t + timedelta(minutes=90), "ad_overwrite"),
    ]


def day_slots(day: date, ads: list) -> list[tuple[datetime, str]]:
    norm_ads = _normalize_ads(ads)
    ads_today = [ad for ad in norm_ads if ad["time"].date() == day]

    raw_overwrites: list[tuple[datetime, str]] = []
    for ad in ads_today:
        raw_overwrites.extend(overwrite_slots(ad))

    overwrites: list[tuple[datetime, str]] = []
    for moment, reason in raw_overwrites:
        if not in_blackout(moment, norm_ads):
            overwrites.append((moment, reason))
    overwrites.sort(key=lambda x: x[0])

    if not ads_today:
        return [(b, "regular") for b in baseline_slots(day)]

    planned: list[tuple[datetime, str]] = list(overwrites)

    for b in baseline_slots(day):
        if in_blackout(b, norm_ads):
            continue
        if any(abs((b - ow[0]).total_seconds()) < 45 * 60 for ow in overwrites):
            continue
        if any(0 < (ad["time"] - b).total_seconds() < 45 * 60 for ad in norm_ads):
            continue

        count_before = sum(1 for m, _ in planned if m < b)
        if count_before >= DAILY_REGULAR_POSTS:
            continue

        planned.append((b, "regular"))

    planned.sort(key=lambda x: x[0])
    return planned


def _candidate_days(now: datetime) -> list[date]:
    now = now.astimezone(MSK)
    return [now.date(), now.date() + timedelta(days=1)]


def _slot_still_open(now: datetime, day: date, moment: datetime, reason: str) -> bool:
    moment = moment.replace(microsecond=0)
    if reason == "regular":
        window = regular_slot_window(day, moment)
        if not window:
            return now <= moment + LATE_GRACE
        _prepare_from, open_until = window
        return now <= open_until
    grace = OVERWRITE_LATE if reason.startswith("ad_overwrite") or reason.startswith("broadcast_overwrite") else LATE_GRACE
    return now <= moment + grace


def _should_prepare(now: datetime, day: date, publish_at: datetime, reason: str, delta: timedelta, ads: list) -> bool:
    if in_blackout(now, ads):
        return True
    if reason.startswith("broadcast_overwrite"):
        return delta <= BROADCAST_LEAD
    if reason.startswith("ad_overwrite"):
        return delta <= OVERWRITE_LEAD
    window = regular_slot_window(day, publish_at)
    if window:
        prepare_from, open_until = window
        return prepare_from <= now <= open_until
    return -LATE_GRACE <= delta <= REGULAR_LEAD


def next_publish(
    now: datetime,
    ads: list,
    occupied: set[datetime] | None = None,
) -> dict | None:
    now = now.astimezone(MSK)
    taken = {item.astimezone(MSK).replace(microsecond=0) for item in (occupied or set())}
    ads_norm = _normalize_ads(ads)
    found: tuple[datetime, str] | None = None
    found_day: date | None = None
    for day in _candidate_days(now):
        for moment, reason in day_slots(day, ads_norm):
            key = moment.replace(microsecond=0)
            if key in taken:
                continue
            if not _slot_still_open(now, day, key, reason):
                continue
            found = (key, reason)
            found_day = day
            break
        if found:
            break
    if not found or found_day is None:
        return None
    publish_at, reason = found
    delta = publish_at - now
    prepare = _should_prepare(now, found_day, publish_at, reason, delta, ads_norm)
    return {
        "publish_at": publish_at,
        "reason": reason,
        "prepare": prepare,
        "seconds_until": int(delta.total_seconds()),
        "in_blackout_now": in_blackout(now, ads_norm),
    }


def delivery_mode(now: datetime, publish_at: datetime, reason: str, ads: list) -> str:
    now = now.astimezone(MSK)
    publish_at = publish_at.astimezone(MSK)
    blocked = in_blackout(now, ads)
    if blocked:
        if publish_at - now > SCHEDULE_BUFFER:
            return "schedule"
        if publish_at > now:
            return "wait_then_send"
        return "abort_blackout"
    if (reason.startswith("ad_overwrite") or reason.startswith("broadcast_overwrite")) and publish_at - now > SCHEDULE_BUFFER:
        return "schedule"
    return "send"
