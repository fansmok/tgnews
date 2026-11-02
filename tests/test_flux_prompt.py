from newsagent.flux import FluxUnavailable, build_prompt, render_card, timeout_error


def test_prompt_uses_content_board_and_centers_the_news_photo():
    text = build_prompt(
        {"title": "English title"},
        {"title": "Винисиус думает об уходе"},
        "quote",
        {"quote": "Я хочу играть", "attribution": "Винисиус", "score": "", "amount": "", "stat_value": ""},
    )
    assert text.startswith("Image 1 — это контент-борд канала")
    assert "использовать как референс" in text
    assert "Image 2 — фото новости" in text
    assert "апскейл" in text.lower()
    assert "фигуру, которая указана на этом фото" in text
    assert "шаблон «Цитата»" in text
    assert "по-русски" in text
    assert "Картинка строго без логотипов" in text
    assert "В верхней шапке НЕ пиши GOL88.RU" in text
    assert "GOL88.RU" in text
    assert "#D4BA5B" in text
    assert "плашку-капсулу" in text
    assert "#0B5D28" in text
    assert "контровой свет" in text
    assert "Не пиши просмотры, дату и время" in text
    assert "«Я хочу играть»" in text


def test_prompt_picks_result_transfer_or_plain_photo():
    result = build_prompt({}, {"title": "Сити победил"}, "result", {"quote": "", "score": "2 : 1", "amount": ""})
    transfer = build_prompt({}, {"title": "Переход закрыт"}, "transfer", {"quote": "", "score": "", "amount": "45 млн евро"})
    plain = build_prompt({}, {"title": "Тренер продлил контракт"}, "main", {"quote": "", "score": "", "amount": ""})
    assert "результат матча" in result
    assert "2 : 1" in result
    assert "трансфер" in transfer
    assert "45 млн евро" in transfer
    assert "просто фото с текстом" in plain
    assert "не придумывай" in plain
    assert "Бейдж только «НОВОСТЬ»" in plain
    assert "Бейдж «СРОЧНО» не ставь" in plain
    urgent = build_prompt({}, {"title": "Тренер уволен"}, "urgent", {"quote": "", "score": "", "amount": ""})
    assert "Бейдж только «НОВОСТЬ»" not in urgent


def test_timeout_retries_the_card_once(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake(photo, reference, prompt, dest, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise FluxUnavailable("generate task timeout")
        return {"task_id": "ok", "width": 600, "height": 600, "model": "nano-banana-2-1", "resolution": "1K"}

    monkeypatch.setattr("newsagent.flux._render_once", fake)
    result = render_card(tmp_path / "photo.jpg", None, "prompt", tmp_path / "designed.jpg")
    assert calls["n"] == 2
    assert result["task_id"] == "ok"
    assert timeout_error("generation timed out") is True


def test_errors_are_retried_up_to_4_times_and_raise_on_fourth_failure(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake(photo, reference, prompt, dest, **_kwargs):
        calls["n"] += 1
        raise FluxUnavailable("upload failed")

    monkeypatch.setattr("newsagent.flux._render_once", fake)
    failed = False
    try:
        render_card(tmp_path / "photo.jpg", None, "prompt", tmp_path / "designed.jpg")
    except FluxUnavailable:
        failed = True
    assert failed is True
    assert calls["n"] == 4


def test_fallback_produces_plain_photo_600x600(tmp_path, monkeypatch):
    import sys
    from PIL import Image
    from newsagent.runtime import write_json, read_json

    source = Image.new("RGB", (1200, 800), (40, 80, 120))
    source.save(tmp_path / "photo.jpg")
    write_json(tmp_path / "story.json", {"title": "Новость", "action": "news"})
    write_json(tmp_path / "photo.json", {"status": "ok", "file": "photo.jpg", "width": 1200, "height": 800})
    write_json(tmp_path / "copy.json", {"title": "Заголовок", "paragraphs": ["Текст"], "bold_spans": ["Текст"]})

    def fake_render(*args, **kwargs):
        raise FluxUnavailable("mocked failure")

    monkeypatch.setattr("newsagent.flux.render_card", fake_render)
    monkeypatch.setattr(sys, "argv", ["compose_photo.py", "--run-dir", str(tmp_path)])

    from newsagent.runtime import repo_root
    sys.path.insert(0, str(repo_root() / "scripts"))
    import compose_photo
    compose_photo.main()

    design = read_json(tmp_path / "design.json")
    assert design["status"] == "ok"
    assert design["engine"] == "photo"
    assert "flux_error" in design
    out = Image.open(tmp_path / "designed.jpg")
    assert out.size == (600, 600)
