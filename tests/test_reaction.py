from newsagent.copytext import reaction_missing_words


TITLE = "Агент Батракова отреагировал на слова Ротенберга о трансфере в «Галатасарай»"
PARAGRAPHS = ["Интересы футболиста представляет Владимир Кузьмичев."]
AGENT_QUOTE = {
    "text": "У него другая позиция, у нас своя. Нужно глубже посвятить болельщиков в вопрос",
    "author": "Владимир Кузьмичев",
}


def test_reaction_without_the_first_words_is_rejected():
    assert reaction_missing_words(TITLE, PARAGRAPHS, AGENT_QUOTE) == "Ротенберга"


def test_reaction_passes_when_the_first_speaker_is_quoted():
    quote = {"text": "Батраков нам не подходит", "author": "Борис Ротенберг"}
    assert reaction_missing_words(TITLE, PARAGRAPHS, quote) == ""


def test_plain_news_is_not_a_reaction():
    assert reaction_missing_words("Галатасарай интересуется Батраковым", ["Клуб готовит предложение."], None) == ""
