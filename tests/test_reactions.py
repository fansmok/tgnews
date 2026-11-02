from newsagent.reactions import has_foreign_emoji, split_comment


def test_allowed_reaction_with_variation_selector_is_not_foreign():
    assert has_foreign_emoji("Да 👍️") is False
    parts, foreign = split_comment("Да 👍️")
    assert foreign is False
    assert any(part.get("custom_emoji_id") for part in parts)


def test_non_reaction_emoji_is_foreign():
    assert has_foreign_emoji("Гол ⚽️") is True
