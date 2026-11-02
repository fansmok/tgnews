from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
from PIL import Image, ImageOps

API = "https://api.kie.ai"
UPLOAD = "https://kieai.redpandaai.co"
MODEL = "nano-banana-2-1"
OUT = 600
CARD_KIND = {
    "main": "просто фото с текстом, шаблон «Главная новость»",
    "urgent": "срочная новость, шаблон «Срочная новость»",
    "transfer": "трансфер, шаблон «Трансфер»",
    "insider": "инсайд, шаблон «Инсайд»",
    "quote": "цитата, шаблон «Цитата»",
    "result": "результат матча, шаблон «Результат матча»",
    "fixture": "анонс матча, шаблон «Предстоящий матч»",
    "stats": "статистика, шаблон «Статистика»",
    "scandal": "скандал, шаблон «Скандал»",
    "meme": "мем, шаблон «Мем»",
}


class FluxUnavailable(RuntimeError):
    pass


def _key() -> str:
    key = os.environ.get("KIE_API_KEY", "").strip()
    if not key:
        raise FluxUnavailable("KIE_API_KEY is empty")
    return key


def _model() -> str:
    return os.environ.get("KIE_MODEL", "").strip() or MODEL


TEMPLATE_ART = {
    "main": (
        "Крупный поясной портрет игрока в верхних двух третях кадра, внизу плотная тёмно-зелёная плашка с градиентом. "
        "Слева над заголовком жёлтый бейдж «НОВОСТЬ». Имя героя и название клуба в заголовке выдели жёлтым #FFD100, остальной текст ярко-белым."
    ),
    "urgent": (
        "Экстренная подача: слева вертикальный красный световой акцент, красный бейдж «СРОЧНО» белыми буквами, "
        "высокий драматический контраст на лице героя и крупный белый заголовок."
    ),
    "transfer": (
        "Трансферный постер: вокруг фигуры игрока тонкая технологичная HUD-рамка с золотым и изумрудным свечением, "
        "бейдж «ТРАНСФЕР» со стрелками обмена, клуб и фамилию игрока выдели жёлтым #FFD100."
    ),
    "insider": (
        "Инсайдерская подача: изумрудный контровой свет вокруг силуэта, зелёный бейдж «ИНСАЙД», "
        "глубокий тёмный фон с мягкой стадионной дымкой и крупный заголовок."
    ),
    "quote": (
        "Карточка цитаты: выразительный портрет спикера сбоку или в верхних двух третях, жёлтый бейдж «ЦИТАТА», "
        "крупные золотые кавычки « », текст цитаты чистым белым шрифтом и подпись автора жёлтым снизу."
    ),
    "result": (
        "Табло результата матча: динамичный кадр матча, по центру плашки очень крупный жёлтый счёт #FFD100, "
        "рядом названия команд белым шрифтом, сверху бейдж «РЕЗУЛЬТАТ»."
    ),
    "fixture": (
        "Афиша матча: драматический вечерний свет стадиона, бейдж «МАТЧ», крупная вывеска команд и чистое спортивное оформление."
    ),
    "stats": (
        "Карточка статистики: портрет игрока и один главный цифровой показатель огромным жёлтым шрифтом #FFD100 рядом с коротким пояснением."
    ),
    "scandal": (
        "Конфликт и напряжение: жёсткий контрастный свет, красный бейдж «СКАНДАЛ», красная акцентная черта под заголовком."
    ),
    "meme": (
        "Живой ироничный кадр с жёлтым бейджем «ФУТБОЛ» и крупной панчлайн-подписью."
    ),
}


def build_prompt(story: dict, copy: dict, template: str, facts: dict) -> str:
    headline = (copy.get("title") or story.get("title") or "").strip()
    quote = (facts.get("quote") or "").strip()
    author = (facts.get("attribution") or "").strip()
    score = (facts.get("score") or "").strip()
    amount = (facts.get("amount") or "").strip()
    kind = CARD_KIND.get(template, CARD_KIND["main"])
    art = TEMPLATE_ART.get(template, TEMPLATE_ART["main"])
    lines = [
        "Image 1 — это контент-борд канала. Его нужно использовать как референс. Ориентируйся на него: цвета, рамка, бейдж и один подходящий шаблон.",
        "Не копируй весь борд, палитру, чужие примеры, кота и чужие заголовки.",
        f"Нужная картинка: {kind}.",
        "Никаких логотипов не ставь: ни эмблем FC, ни эмблем клубов, ни значков СМИ. Картинка строго без логотипов.",
        "Image 2 — фото новости. Сделай апскейл. Выведи в центр кадра фигуру, которая указана на этом фото. Сохрани лицо, форму и реальный момент. Не подменяй человека.",
        "Визуальная подача: премиальный постер спортивной трансляции в палитре #0B5D28 (глубокий зелёный), #133F27 (тёмная плашка), #0B0B0D (чёрный) и #FFD100 (яркое золото). Добавь деликатный золотисто-изумрудный контровой свет по контуру фигуры, мягкое боке стадионных прожекторов на фоне и тонкую золотую рамку с угловыми акцентами по периметру карточки.",
        f"Композиция шаблона: {art}",
        "Собери одну квадратную карточку.",
        "Весь текст карточки только по-русски и дословно. Ничего не переводи. Шрифт плотный геометрический гротеск как Montserrat ExtraBold, идеальная резкость букв без искажений.",
        "В верхней шапке НЕ пиши GOL88.RU и не ставь никаких плашек — верх оставь абсолютно чистым.",
        "Ссылка на бренд: в нижней части карточки по центру (или снизу) размести аккуратную компактную тёмную плашку-капсулу с надписью «GOL88.RU»: строгий геометрический гротеск без засечек Montserrat Bold, сдержанный золотистый цвет #D4BA5B (матовое золото), в точности как аккуратная ссылка внизу на референсе. Нигде больше GOL88.RU не дублируй.",
        "Не пиши просмотры, дату и время. Эти цифры с контент-борда не публикуй.",
        f"Заголовок дословно: {headline}",
    ]
    if quote:
        who = f" Автор: {author}." if author else ""
        lines.append(f"Вставь цитату дословно: «{quote}».{who}")
    if template == "result" and score:
        lines.append(f"Вставь только этот счёт: {score}")
    elif template == "transfer" and amount:
        lines.append(f"Вставь только эту цифру: {amount}")
    elif template == "stats" and (facts.get("stat_value") or "").strip():
        lines.append(f"Вставь только этот показатель: {facts['stat_value'].strip()}")
    elif not quote:
        lines.append("Цитату, счёт и сумму не придумывай.")
    if template == "main":
        lines.append("Бейдж только «НОВОСТЬ». Бейдж «СРОЧНО» не ставь: это чужой пример с контент-борда.")
    return "\n".join(lines)


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {_key()}"}


def upload_image(path: Path) -> str:
    with path.open("rb") as handle:
        response = httpx.post(
            f"{UPLOAD}/api/file-stream-upload",
            headers=_auth(),
            files={"file": (path.name, handle, "image/jpeg")},
            data={"uploadPath": "newsagent", "fileName": f"{int(time.time())}-{path.name}"},
            timeout=60,
        )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success") or payload.get("code") != 200:
        raise FluxUnavailable(payload.get("msg") or "upload failed")
    data = payload.get("data") or {}
    url = data.get("downloadUrl") or data.get("fileUrl") or data.get("url")
    if not url:
        raise FluxUnavailable("upload returned no url")
    return str(url)


def _create_task(image_urls: list[str], prompt: str) -> str:
    response = httpx.post(
        f"{API}/api/v1/jobs/createTask",
        headers={**_auth(), "Content-Type": "application/json"},
        json={
            "model": _model(),
            "input": {
                "prompt": prompt[:20000],
                "image_input": image_urls,
                "aspect_ratio": "1:1",
                "resolution": "1K",
                "output_format": "jpg",
            },
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200:
        raise FluxUnavailable(payload.get("msg") or "createTask failed")
    task_id = ((payload.get("data") or {}).get("taskId") or "").strip()
    if not task_id:
        raise FluxUnavailable("createTask returned no taskId")
    return task_id


# Kie удаляет загруженные файлы через 24 часа.
REFERENCE_TTL = 20 * 3600


def upload_reference_cached(reference: Path) -> str:
    import hashlib

    cache_path = reference.parent / ".reference_url_cache.json"
    content = reference.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            fresh = time.time() - float(cached.get("uploaded_at") or 0) < REFERENCE_TTL
            if cached.get("hash") == digest and cached.get("url") and fresh:
                return str(cached["url"])
        except Exception:
            pass
    url = upload_image(reference)
    try:
        cache_path.write_text(json.dumps({"hash": digest, "url": url, "uploaded_at": time.time()}), encoding="utf-8")
    except Exception:
        pass
    return url


def _wait(task_id: str, timeout: float = 240) -> str:
    deadline = time.time() + timeout
    delay = 2.5
    while time.time() < deadline:
        response = httpx.get(
            f"{API}/api/v1/jobs/recordInfo",
            headers=_auth(),
            params={"taskId": task_id},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 200:
            raise FluxUnavailable(payload.get("msg") or "recordInfo failed")
        data = payload.get("data") or {}
        state = data.get("state") or ""
        if state == "success":
            raw = data.get("resultJson") or "{}"
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            urls = parsed.get("resultUrls") or []
            if not urls:
                raise FluxUnavailable("result has no image")
            return str(urls[0])
        if state == "fail":
            raise FluxUnavailable(data.get("failMsg") or "generation failed")
        time.sleep(delay)
        delay = min(4.0, delay * 1.25)
    raise FluxUnavailable("generation timed out")


def timeout_error(message: str) -> bool:
    lowered = message.lower()
    return "timeout" in lowered or "timed out" in lowered


RENDER_BUDGET = 420
ATTEMPT_WAIT = 150


def _render_once(photo: Path, reference: Path | None, prompt: str, dest: Path, wait_timeout: float = ATTEMPT_WAIT) -> dict:
    urls = []
    if reference is not None:
        urls.append(upload_reference_cached(reference))
    urls.append(upload_image(photo))
    task_id = _create_task(urls, prompt)
    result_url = _wait(task_id, timeout=wait_timeout)
    response = httpx.get(result_url, timeout=60, follow_redirects=True)
    response.raise_for_status()
    raw = dest.with_suffix(".flux.jpg")
    raw.write_bytes(response.content)
    image = Image.open(raw).convert("RGB")
    fitted = ImageOps.fit(image, (OUT, OUT), method=Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fitted.save(dest, quality=92, subsampling=0)
    raw.unlink(missing_ok=True)
    return {"task_id": task_id, "width": OUT, "height": OUT, "model": _model(), "resolution": "1K"}


def render_card(photo: Path, reference: Path | None, prompt: str, dest: Path, budget: float = RENDER_BUDGET) -> dict:
    """До 4 попыток Nano Banana в общем бюджете времени; не уложились — исключение, и берётся обычное фото."""
    deadline = time.monotonic() + budget
    error: Exception | None = None
    for attempt in range(4):
        remaining = deadline - time.monotonic()
        if remaining < 20:
            break
        try:
            return _render_once(photo, reference, prompt, dest, wait_timeout=min(ATTEMPT_WAIT, remaining))
        except Exception as exc:  # noqa: BLE001
            error = exc
            if attempt < 3:
                time.sleep(5)
    raise error or FluxUnavailable("generation budget exhausted")
