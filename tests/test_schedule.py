from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from newsagent.schedule import (
    DAILY_REGULAR_POSTS,
    baseline_slots,
    batch_slots,
    day_slots,
    delivery_mode,
    next_publish,
    regular_slot_window,
    relocation_plan,
)

MSK = ZoneInfo("Europe/Moscow")
DAY = date(2026, 10, 22)


def at(hour: int, minute: int, day: int = 22, kind: str = "regular") -> dict:
    dt = datetime(2026, 10, day, hour, minute, tzinfo=MSK)
    return {"time": dt, "kind": kind}


def labels(slots):
    return [item.strftime("%H:%M") for item, _reason in slots]


def test_baseline_day_without_ads_has_four_windows():
    slots = day_slots(DAY, [])
    assert len(slots) == DAILY_REGULAR_POSTS
    assert all(reason == "regular" for _item, reason in slots)
    moments = [item for item, _ in slots]
    assert moments == sorted(moments)
    for moment in moments:
        assert regular_slot_window(DAY, moment) is not None
        assert moment.hour <= 22 or (moment.hour == 22 and moment.minute <= 30)
    first = moments[0]
    assert (first.hour, first.minute) >= (9, 30)
    assert (first.hour, first.minute) <= (10, 30)
    assert (moments[1].hour, moments[1].minute) >= (13, 30)
    assert (moments[1].hour, moments[1].minute) <= (14, 30)
    assert (moments[2].hour, moments[2].minute) >= (16, 30)
    assert (moments[3].hour, moments[3].minute) >= (19, 30)
    assert (moments[3].hour, moments[3].minute) <= (20, 30)


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
    regulars = [item for item, reason in slots if reason == "regular"]
    assert all(not (item.hour == 11) for item in regulars)


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


def test_first_post_does_not_start_before_0930():
    target = baseline_slots(DAY)[0]
    assert (target.hour, target.minute) >= (9, 30)
    assert (target.hour, target.minute) <= (10, 30)
    too_early = datetime(DAY.year, DAY.month, DAY.day, 9, 0, tzinfo=MSK)
    early = next_publish(too_early, [], set())
    assert early is not None
    assert early["publish_at"] == target
    assert early["prepare"] is False
    opened = datetime(DAY.year, DAY.month, DAY.day, 9, 30, tzinfo=MSK)
    ready = next_publish(opened, [], set())
    assert ready is not None
    assert ready["publish_at"] == target
    assert ready["prepare"] is True


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


def test_morning_batch_lists_all_four_future_slots():
    morning = datetime(DAY.year, DAY.month, DAY.day, 8, 30, tzinfo=MSK)
    slots = batch_slots(morning, [])
    assert len(slots) == 4
    assert [item["reason"] for item in slots] == ["regular"] * 4
    assert slots[0]["publish_at"].hour < 11
    assert slots[-1]["publish_at"].hour >= 19


def test_batch_does_not_start_before_morning():
    assert batch_slots(datetime(DAY.year, DAY.month, DAY.day, 7, 0, tzinfo=MSK), []) == []


def test_two_ads_fill_every_overwrite_in_one_batch():
    afternoon = datetime(DAY.year, DAY.month, DAY.day, 12, 0, tzinfo=MSK)
    slots = batch_slots(afternoon, [at(13, 0), at(15, 0)])
    overwrites = [item for item in slots if item["reason"] == "ad_overwrite"]
    assert len(overwrites) == 4
    taken = {overwrites[0]["publish_at"], overwrites[1]["publish_at"]}
    rest = batch_slots(afternoon, [at(13, 0), at(15, 0)], taken)
    assert len([item for item in rest if item["reason"] == "ad_overwrite"]) == 2


def test_evening_ad_keeps_standing_day_posts_and_adds_two_after_the_hour():
    now = datetime(DAY.year, DAY.month, DAY.day, 18, 0, tzinfo=MSK)
    standing = set(baseline_slots(DAY))
    ad = [at(22, 0)]
    fresh = batch_slots(now, ad, standing)
    assert [(item["publish_at"].strftime("%H:%M"), item["reason"]) for item in fresh] == [
        ("23:00", "ad_overwrite"),
        ("23:30", "ad_overwrite"),
    ]
    scheduled = [
        {"publish_at": moment, "message_id": str(index), "run_id": f"R-{index}"}
        for index, moment in enumerate(sorted(standing))
    ]
    assert relocation_plan(now, ad, scheduled) == []


def test_blocked_post_moves_to_the_next_free_minute():
    now = datetime(DAY.year, DAY.month, DAY.day, 12, 10, tzinfo=MSK)
    blocked = datetime(DAY.year, DAY.month, DAY.day, 13, 40, tzinfo=MSK)
    kept = datetime(DAY.year, DAY.month, DAY.day, 19, 40, tzinfo=MSK)
    plan = relocation_plan(
        now,
        [at(13, 0)],
        [
            {"publish_at": blocked, "message_id": "10", "run_id": "R-old"},
            {"publish_at": kept, "message_id": "11", "run_id": "R-keep"},
        ],
    )
    assert len(plan) == 1
    assert plan[0]["status"] == "move"
    assert plan[0]["from"] == blocked.replace(microsecond=0)
    assert plan[0]["to"] == at(14, 0)["time"]
    assert plan[0]["run_id"] == "R-old"


def test_future_regular_post_is_scheduled():
    assert delivery_mode(at(8, 30)["time"], at(9, 40)["time"], "regular", []) == "schedule"


def test_occupied_slot_moves_forward():
    plan = next_publish(at(11, 10)["time"], [at(11, 0)], {at(12, 0)["time"]})
    assert plan["publish_at"] == at(12, 30)["time"]
    assert plan["reason"] == "ad_overwrite"
