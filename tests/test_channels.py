from newsagent.ads import select_ads
from newsagent.channels import messages_from_updates, parse_public_html


def test_public_channel_html_becomes_moscow_slots():
    html = """
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message_text js-message_text" dir="auto">Реклама сегодня<br/>11:00<br/>21:40 транса</div>
      <time datetime="2026-10-22T05:00:00+00:00"></time>
    </div>
    """
    messages = parse_public_html(html)
    assert select_ads(messages) == [
        "2026-10-22T11:00:00+03:00",
        "2026-10-22T21:40:00+03:00",
    ]


def test_bot_update_from_the_ads_channel_is_kept():
    payload = {
        "ok": True,
        "result": [
            {
                "update_id": 10,
                "channel_post": {
                    "message_id": 4,
                    "date": 1761112800,
                    "text": "Реклама сегодня\n11:00\n15:00",
                    "chat": {"id": -100, "username": "reklaama33333", "type": "channel"},
                },
            }
        ],
    }
    messages, offset = messages_from_updates(payload, "@reklaama33333")
    assert offset == 11
    assert len(messages) == 1
    assert "11:00" in messages[0]["text"]
    ignored, _same_offset = messages_from_updates(payload, "@zzhajakak")
    assert ignored == []
