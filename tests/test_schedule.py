from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from newsagent.schedule import (
    DAILY_REGULAR_POSTS,
    baseline_slots,
    day_slots,
    delivery_mode,
    next_publish,
    regular_slot_window,
)

MSK = ZoneInfo("Europe/Moscow")
DAY = date(2026, 10, 22)


def at(hour: int, minute: int, day: int = 22, kind: str = "regular") -> dict:
    dt = datetime(2026, 10, day, hour, minute, tzinfo=MSK)
    return {"time": dt, "kind": kind}


def labels(slots):
    return [item.strftime("%H:%M") for item, _reason in slots]


def test_baseline_day_without_ads_has_six_flexible_slots_in_bands():
    slots = day_slots(DAY, [])
    assert len(slots) == DAILY_REGULAR_POSTS
    assert all(reason == "regular" for _item, reason in slots)
    moments = [item for item, _ in slots]
    assert moments == sorted(moments)
    for moment in moments:
        assert regular_slot_window(DAY, moment) is not None
        assert moment.hour >= 10
        assert moment.hour <= 22 or (moment.hour == 22 and moment.minute <= 30)


def test_baseline_is_stable_for_the_same_day():
    first = baseline_slots(DAY)
    second = baseline_slots(DAY)
    assert first == second
    assert len(first) == DAILY_REGULAR_POSTS


def test_one_ad_adds_two_overwrites_and_keeps_morning_baseline():
    ads = [at(11, 0)]
    slots = day_slots(DAY, ads)
    reasons = {item.strftime("%H:%M"): reason for item, reason in slots}
    assert reasons.get("12:00") == "ad_overwrite"
    assert reasons.get("12:30") == "ad_overwrite"
    assert "11:00" not in reasons
    assert "11:30" not in reasons
    regular_count = sum(1 for _m, r in slots if r == "regular")
    assert regular_count >= 3


def test_two_ads_expand_with_overwrites():
    slots = day_slots(DAY, [at(13, 0), at(15, 0)])
    overwrite_times = [item for item, reason in slots if reason == "ad_overwrite"]
    assert len(overwrite_times) == 4
    assert labels(slots)[0] == baseline_slots(DAY)[0].strftime("%H:%M")


def test_broadcast_ad_timing():
    slots = day_slots(DAY, [at(21, 40, kind="broadcast")])
    reasons = {item.strftime("%H:%M"): reason for item, reason in slots}
    assert reasons["21:55"] == "broadcast_overwrite"
    assert reasons["22:25"] == "broadcast_overwrite"
    assert reasons["23:10"] == "broadcast_overwrite"


def test_prepare_true_inside_regular_band_even_before_target_minute():
    target = baseline_slots(DAY)[0]
    window = regular_slot_window(DAY, target)
    assert window is not None
    band_start, _band_end = window
    probe = band_start + timedelta(seconds=(target - band_start).total_seconds() // 2)
    plan = next_publish(probe, [], set())
    assert plan is not None
    assert plan["reason"] == "regular"
    assert plan["prepare"] is True


def test_during_ad_the_next_post_is_the_exact_overwrite():
    plan = next_publish(at(11, 10)["time"], [at(11, 0)], set())
    assert plan["publish_at"] == at(12, 0)["time"]
    assert plan["reason"] == "ad_overwrite"
    assert plan["prepare"] is True
    assert plan["in_blackout_now"] is True


def test_delivery_never_sends_inside_blackout():
    assert delivery_mode(at(11, 30)["time"], at(12, 0)["time"], "ad_overwrite", [at(11, 0)]) == "schedule"
    assert delivery_mode(at(11, 0)["time"], at(11, 0)["time"], "regular", [at(11, 0)]) == "abort_blackout"


def test_occupied_slot_moves_forward():
    plan = next_publish(at(11, 10)["time"], [at(11, 0)], {at(12, 0)["time"]})
    assert plan["publish_at"] == at(12, 30)["time"]
    assert plan["reason"] == "ad_overwrite"
