# Pipeline fix queue

Открытых инцидентов нет. Custom emoji снова включены и берутся только из RestrictedEmoji, foot_flags_by_fStikBot, NewsEmoji и FC_logos. Тег шаблона main пишется как news. В промпте шаблона main бейдж только «НОВОСТЬ», бейдж «СРОЧНО» запрещён. Размер карточки теперь всегда 600×600, инциденты про 1280×720 и предел 640×360 закрыты этим правилом. Человеку: INC-20261022-1536-fn-ads-other, INC-20261022-1612-fn-ads-other, INC-20261022-1642-fn-ads-other, INC-20261022-1707-fn-ads-other, INC-20261022-1738-fn-ads-other, INC-20261022-1807-fn-ads-other и INC-20261022-1837-fn-ads-other — после тестового дня снова читать канал рекламы, логику рекламы не выключать. INC-20261022-1752-fn-voice-voice — на сухой жалобе опрос Gemini обнулён, промпт голоса не менялся. Клубных тегов в каталоге emoji по-прежнему нет, id не сочинялись.

## INC-20261022-1339-fn-photo-script
status: fixed
run_date: 2026-10-22
role: fn-photo
run_id: R-test-gemini
severity: medium
category: script

### What went wrong
- fetch_photo.py отбросил og:image новости: в URL есть подстрока logo внутри имени файла no_logo_no_text.jpg. Картинка из RSS ответила 404.

### How the agent recovered this run
- Скачал тот же og:image вручную. Кадр принят: игрок Галатасарая в белой форме празднует гол у ворот, на трибунах болельщики.

### Durable fix needed before next run
- Не помечать URL как bad_url, если logo входит в отрицание вроде no_logo.

### Suggested files to inspect/change
- `src/newsagent/photos.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- `url_blocked` не считает bad_url отрицание logo: no_logo, no-logo, nologo, without_logo. Путь с настоящим logo по-прежнему отбрасывается.

## INC-20261022-1342-fn-copy-other
status: fixed
run_date: 2026-10-22
role: fn-copy
run_id: R-test-gemini
severity: low
category: other

### What went wrong
- Gemini поставил emoji в заголовок, символ снят

### How the agent recovered this run
- yes

### Durable fix needed before next run
- заголовок без emoji, значок ставит fn-emoji

### Suggested files to inspect/change
- `scripts/write_copy.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- Промпт требует заголовок без emoji. `normalize` снимает emoji из заголовка и абзацев.

## INC-20261022-1345-fn-emoji-catalog
status: needs-human
run_date: 2026-10-22
role: fn-emoji
run_id: R-test-gemini
severity: low
category: catalog

### What went wrong
- В каталоге нет custom emoji с тегом galatasaray. Тегов goal тоже нет. Набор futbol_klub не ставился.

### How the agent recovered this run
- В заголовок поставлен мяч из futbol_icon: id 5377435673206730908, fallback ⚽️, тег football. Абзацы без emoji.

### Durable fix needed before next run
- Добавить в каталог значок Галатасарая с тегом galatasaray и пересинхронизировать shared/emoji-catalog.json.

### Suggested files to inspect/change
- `shared/emoji-catalog.json`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- В каталоге нет тега galatasaray и нет ключевых слов набора futbol_klub. Id не сочинялись. Нужны ключевые слова набора, затем синхронизация shared/emoji-catalog.json.

## INC-20261022-1351-fn-copy-other
status: fixed
run_date: 2026-10-22
role: fn-copy
run_id: R-test-gemini
severity: medium
category: other

### What went wrong
- Gemini добавил минуту гола и расширил цитату сверх источника

### How the agent recovered this run
- yes

### Durable fix needed before next run
- текст сужен до заголовка и summary

### Suggested files to inspect/change
- `scripts/write_copy.py`
- `src/newsagent/copytext.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- Если текст страницы похож на меню, он не входит в источник. Промпт запрещает факты вне title и summary.

## INC-20261022-1536-fn-ads-other
status: needs-human
run_date: 2026-10-22
role: fn-ads
run_id: R-daytest-1535
severity: low
category: other

### What went wrong
- Дневной тест: рекламу не читали по просьбе пользователя, слоты пустые, пост уходит сразу.

### How the agent recovered this run
- plan_slot по пустой сетке

### Durable fix needed before next run
- Вернуть чтение канала рекламы после тестового дня

### Suggested files to inspect/change
- `none`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- Пустой список — приказ дневного теста. Логику рекламы в коде не выключал и не вырезал. После тестового дня снова читать канал рекламы.

## INC-20261022-1544-fn-design-other
status: needs-human
run_date: 2026-10-22
role: fn-design
run_id: R-daytest-1535
severity: low
category: other

### What went wrong
- Исходник photo.jpg 1200×630 меньше окна landscape. Холст уменьшен до feed-1280x720-fit 1120×630, scale 0.875.

### How the agent recovered this run
- Карточка собрана шаблоном urgent: бейдж СРОЧНО, красная полоса, логотип FC не закрывает лицо Нагельсманна.

### Durable fix needed before next run
- Для ленты без уменьшения нужен исходник не меньше 1280×720.

### Suggested files to inspect/change
- `memory/runs/R-daytest-1535/design.json`
- `memory/runs/R-daytest-1535/designed.jpg`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- Холст уменьшен по правилу макета: исходник меньше окна, фото не увеличиваем. Код не менялся. Для ленты без уменьшения нужен исходник не меньше 1280×720.

## INC-20261022-1551-fn-emoji-catalog
status: needs-human
run_date: 2026-10-22
role: fn-emoji
run_id: R-daytest-1535
severity: low
category: catalog

### What went wrong
- В каталоге нет custom emoji с тегом man-utd: значка «Манчестер Юнайтед» нет, keywords у всех items пустые, клубные теги не проставлены.

### How the agent recovered this run
- В заголовок поставлен мяч из futbol_icon: id 5377435673206730908, fallback ⚽️, тег football. Набор futbol_klub и чужие клубы не ставились. Абзац про Нагельсманна без emoji: это не увольнение, не цитата, не травма и не трансфер.

### Durable fix needed before next run
- Проставить keywords клубов при sync emoji и добавить в каталог значок Manchester United с тегом man-utd.

### Suggested files to inspect/change
- `shared/emoji-catalog.json`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- В каталоге нет тега man-utd, keywords пустые. Id значка «Манчестер Юнайтед» не сочинялся. Нужны настоящий custom emoji id и ключевые слова набора, затем синхронизация shared/emoji-catalog.json.

## INC-20261022-1559-fn-copy-other
status: fixed
run_date: 2026-10-22
role: fn-copy
run_id: R-daytest-1535
severity: low
category: other

### What went wrong
- Критик вернул текст: в абзаце не было жирного факта

### How the agent recovered this run
- В bold_spans добавлен уже существующий кусок про Нагельсманна

### Durable fix needed before next run
- Просить Gemini сразу класть ключевое имя в bold_spans

### Suggested files to inspect/change
- `none`

### Secrets
- none recorded

### Fixer resolution
- fixed
- Промпт и редактура просят класть в bold_spans ключевое имя человека из абзаца, если нет счёта, суммы, минуты или срока. Имя — точная подстрока абзаца, не выдумка.

## INC-20261022-1612-fn-ads-other
status: needs-human
run_date: 2026-10-22
role: fn-ads
run_id: R-daytest-1612
severity: low
category: other

### What went wrong
- Дневной тест: рекламу не читали, слоты пустые, пост уходит сразу.

### How the agent recovered this run
- plan_slot по пустой сетке

### Durable fix needed before next run
- Вернуть чтение канала рекламы после тестового дня

### Suggested files to inspect/change
- `none`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- Пустой список — приказ дневного теста. Логику рекламы в коде не выключал и не вырезал. После тестового дня снова читать канал рекламы.

## INC-20261022-1622-fn-memory-script
status: fixed
run_date: 2026-10-22
role: fn-memory
run_id: R-daytest-1612
severity: medium
category: script

### What went wrong
- pick_story пропустил повтор Батракова и «Галатасарая»: похожесть заголовков 0.43, event_key другой (transfer против result). Английский пересказ про Кэррика и «МЮ» тоже не совпал с уже отправленным сюжетом message 271.

### How the agent recovered this run
- Оба URL записаны в exclude.json, pick_story запущен снова. Выбран новый сюжет: агент Винисиуса о переходе в «Арсенал».

### Durable fix needed before next run
- Считать дублем тот же клуб и того же игрока в тот же день, даже если угол заголовка и event_key различаются. Английский пересказ уже вышедшего сюжета отсекать по клубу и событию, не только по похожести заголовка.

### Suggested files to inspect/change
- `src/newsagent/memory.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- `is_duplicate` считает дублем тот же день, общий клуб и общее имя в заголовке, даже если действие и event_key разные. Склонение и латиница сходятся по согласным. Другой игрок того же клуба не отсекается.

## INC-20261022-1631-fn-emoji-catalog
status: needs-human
run_date: 2026-10-22
role: fn-emoji
run_id: R-daytest-1612
severity: low
category: catalog

### What went wrong
- В каталоге нет custom emoji с тегами real-madrid и arsenal: значков «Реала» и «Арсенала» нет, keywords у items пустые, клубные теги не проставлены. Значок Винисиуса в World_Football_players тоже не отличить — все items набора с тегом football.

### How the agent recovered this run
- В заголовок поставлен мяч из futbol_icon: id 5377435673206730908, fallback ⚽️, тег football. Набор futbol_klub и чужие клубы не ставились. Абзац без emoji: это слух о рассматривавшемся переходе, не свершившийся трансфер, не цитата и не травма.

### Durable fix needed before next run
- Проставить keywords клубов при sync emoji и добавить в каталог значки Real Madrid (тег real-madrid) и Arsenal (тег arsenal).

### Suggested files to inspect/change
- `shared/emoji-catalog.json`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- В каталоге нет тегов real-madrid и arsenal, keywords пустые. Id значков «Реала», «Арсенала» и Винисиуса не сочинялись. Нужны настоящие custom emoji id и ключевые слова набора, затем синхронизация shared/emoji-catalog.json.

## INC-20261022-1642-fn-ads-other
status: needs-human
run_date: 2026-10-22
role: fn-ads
run_id: R-daytest-1642
severity: low
category: other

### What went wrong
- Дневной тест: рекламу не читали, слоты пустые, пост уходит сразу.

### How the agent recovered this run
- plan_slot по пустой сетке

### Durable fix needed before next run
- Вернуть чтение канала рекламы после тестового дня

### Suggested files to inspect/change
- `none`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- Пустой список — приказ дневного теста. Логику рекламы в коде не выключал и не вырезал. После тестового дня снова читать канал рекламы.

## INC-20261022-1654-fn-emoji-catalog
status: needs-human
run_date: 2026-10-22
role: fn-emoji
run_id: R-daytest-1642
severity: low
category: catalog

### What went wrong
- В каталоге нет custom emoji с тегом real-madrid: значка «Реала» нет, keywords у всех items пустые, клубные теги не проставлены. Ямаль, Родри, Кейн и Мбаппе в World_Football_players не отличить — у набора только тег football. Тега ballon-dor тоже нет.

### How the agent recovered this run
- В заголовок поставлен мяч из futbol_icon: id 5377435673206730908, fallback ⚽️, тег football. Набор futbol_klub и чужие клубы не ставились. Абзац без emoji: это заявление про трофей, не отдельная цитата в абзаце, не травма и не трансфер. Цитата рендерится отдельным блоком без слота emoji.

### Durable fix needed before next run
- Проставить keywords клубов и игроков при sync emoji и добавить в каталог значок Real Madrid с тегом real-madrid, а также различимые id Ямаля, Родри, Кейна и Мбаппе.

### Suggested files to inspect/change
- `shared/emoji-catalog.json`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- В каталоге нет тега real-madrid, keywords пустые, Ямаль, Родри, Кейн и Мбаппе неразличимы, тега ballon-dor нет. Id значков не сочинялись. Нужны настоящие custom emoji id и ключевые слова набора, затем синхронизация shared/emoji-catalog.json.

## INC-20261022-1655-fn-design-other
status: needs-human
run_date: 2026-10-22
role: fn-design
run_id: R-daytest-1642
severity: low
category: other

### What went wrong
- Исходник photo.jpg 1200×630 меньше окна landscape. Холст уменьшен до feed-1280x720-fit 1120×630, scale 0.875.

### How the agent recovered this run
- Карточка собрана шаблоном quote: бейдж ЦИТАТА, жёлтая кавычка, слова Гути. Логотип FC снизу слева не закрывает лицо.

### Durable fix needed before next run
- Для ленты без уменьшения нужен исходник не меньше 1280×720.

### Suggested files to inspect/change
- `memory/runs/R-daytest-1642/design.json`
- `memory/runs/R-daytest-1642/designed.jpg`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- Холст уменьшен по правилу макета: исходник 1200×630 меньше окна, фото не растягивалось. Код не менялся. Для ленты без уменьшения нужен исходник не меньше 1280×720.

## INC-20261022-1707-fn-ads-other
status: needs-human
run_date: 2026-10-22
role: fn-ads
run_id: R-daytest-1707
severity: low
category: other

### What went wrong
- Дневной тест: рекламу не читали, слоты пустые, пост уходит сразу.

### How the agent recovered this run
- plan_slot по пустой сетке

### Durable fix needed before next run
- Вернуть чтение канала рекламы после тестового дня

### Suggested files to inspect/change
- `none`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- Пустой список — приказ дневного теста. Логику рекламы в коде не выключал и не вырезал. После тестового дня снова читать канал рекламы.

## INC-20261022-1720-fn-design-other
status: needs-human
run_date: 2026-10-22
role: fn-design
run_id: R-daytest-1707
severity: low
category: other

### What went wrong
- Исходник photo.jpg 1200×630 меньше окна landscape. Холст уменьшен до feed-1280x720-fit 1120×630, scale 0.875.

### How the agent recovered this run
- Карточка собрана шаблоном urgent: бейдж СРОЧНО, красная полоса, заголовок про Луиса Диаса. Логотип FC снизу слева не закрывает лицо.

### Durable fix needed before next run
- Для ленты без уменьшения нужен исходник не меньше 1280×720.

### Suggested files to inspect/change
- `memory/runs/R-daytest-1707/design.json`
- `memory/runs/R-daytest-1707/designed.jpg`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- Холст уменьшен по правилу макета: исходник 1200×630 меньше окна, фото не растягивалось. Код не менялся. Для ленты без уменьшения нужен исходник не меньше 1280×720.

## INC-20261022-1720-fn-emoji-catalog
status: needs-human
run_date: 2026-10-22
role: fn-emoji
run_id: R-daytest-1707
severity: low
category: catalog

### What went wrong
- В каталоге нет custom emoji с тегами bayern и arsenal: значков «Баварии» и «Арсенала» нет, keywords у всех items пустые, клубные теги не проставлены. Тега injury тоже нет. Значок Луиса Диаса в World_Football_players не отличить — у набора только тег football.

### How the agent recovered this run
- В заголовок поставлен мяч из futbol_icon: id 5377435673206730908, fallback ⚽️, тег football. Набор futbol_klub и чужие клубы не ставились. Абзац без emoji: это та же травма, что в заголовке, не отдельная цитата и не трансфер.

### Durable fix needed before next run
- Проставить keywords клубов при sync emoji и добавить в каталог значки Bayern (тег bayern) и Arsenal (тег arsenal), а также emoji травмы с тегом injury.

### Suggested files to inspect/change
- `shared/emoji-catalog.json`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- В каталоге нет тегов bayern, arsenal и injury, keywords пустые, значок Луиса Диаса не отличить. Id не сочинялись. Нужны настоящие custom emoji id и ключевые слова набора, затем синхронизация shared/emoji-catalog.json.

## INC-20261022-1738-fn-ads-other
status: needs-human
run_date: 2026-10-22
role: fn-ads
run_id: R-daytest-1738
severity: low
category: other

### What went wrong
- Дневной тест: рекламу не читали, слоты пустые, пост уходит сразу.

### How the agent recovered this run
- plan_slot по пустой сетке

### Durable fix needed before next run
- Вернуть чтение канала рекламы после тестового дня

### Suggested files to inspect/change
- `none`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- Пустой список — приказ дневного теста. Логику рекламы не выключал. После тестового дня снова читать канал рекламы.

## INC-20261022-1746-fn-memory-script
status: fixed
run_date: 2026-10-22
role: fn-memory
run_id: R-daytest-1738
severity: medium
category: script

### What went wrong
- pick_story счёл новым второй URL травмы Луиса Диаса и «Баварии» (championat), хотя тот же сюжет sports.ru уже в базе со статусом sent. Похожесть заголовков 0.20, Жаккар 0.07. event_key совпал (2026-10-22|injury|arsenal,bayern), но действие не result, поэтому порог события 0.4 не сработал. Фамилия «Диас» короче 5 букв и не попала в сверку игрока, остов «Диаса» — «дс» короче 4 согласных.

### How the agent recovered this run
- URL championat записан в exclude.json, pick_story запущен снова. Выбран новый сюжет: жалоба Высшего совета Испании на Тебаса из-за сравнений ТВ «Реала». Повторы Батракова, Кэррика, Винисиуса, Диаса и выходного «МЮ» после «Комо» отсечены.

### Durable fix needed before next run
- Узнавать короткие фамилии вроде Диас/Диаса/Dias при сверке того же игрока и клуба за день. Одинаковый event_key травмы с теми же клубами считать дублем, даже если Жаккар заголовков ниже 0.4.

### Suggested files to inspect/change
- `src/newsagent/memory.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- Короткая фамилия с заглавной (Диас, Диаса, Dias) даёт остов из двух согласных и сходится с тем же клубом за день. Клубные слова вроде Комо и Реала игроком не считаются. Другой игрок тех же клубов вторым URL не отсекается.

## INC-20261022-1752-fn-emoji-catalog
status: needs-human
run_date: 2026-10-22
role: fn-emoji
run_id: R-daytest-1738
severity: low
category: catalog

### What went wrong
- В каталоге нет custom emoji с тегом real-madrid: значка «Реала» нет, keywords у всех items пустые, клубные теги не проставлены. Тега la liga тоже нет.

### How the agent recovered this run
- В заголовок поставлен мяч из futbol_icon: id 5377435673206730908, fallback ⚽️, тег football. Набор futbol_klub и чужие клубы не ставились. Абзац без emoji: это та же жалоба на Тебаса, не отдельная цитата, не травма и не трансфер.

### Durable fix needed before next run
- Проставить keywords клубов при sync emoji и добавить в каталог значок Real Madrid с тегом real-madrid.

### Suggested files to inspect/change
- `shared/emoji-catalog.json`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- В каталоге нет тега real-madrid. Id не сочинялись.

## INC-20261022-1752-fn-voice-voice
status: needs-human
run_date: 2026-10-22
role: fn-voice
run_id: R-daytest-1738
severity: low
category: voice

### What went wrong
- Gemini на сухом институциональном сюжете вернул опрос, стоит ли наказывать за сравнение. Такой опрос и шутка про сравнение запрещены.

### How the agent recovered this run
- comment заменён на null, reason not_needed, engine gemini оставлен.

### Durable fix needed before next run
- Для сухой жалобы суда без развилки болельщика write_voice должен оставлять comment пустым и reason not_needed, без опроса про сравнение.

### Suggested files to inspect/change
- `scripts/write_voice.py`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- В этом выпуске comment обнулён. Промпт write_voice не менялся.

## INC-20261022-1753-fn-design-other
status: needs-human
run_date: 2026-10-22
role: fn-design
run_id: R-daytest-1738
severity: low
category: other

### What went wrong
- Исходник photo.jpg 1200×630 меньше окна landscape. Холст уменьшен до feed-1280x720-fit 1120×630, scale 0.875.

### How the agent recovered this run
- Карточка собрана шаблоном main: жёлтый бейдж НОВОСТЬ, полосы, заголовок про жалобу на Хавьера Тебаса. Логотип FC снизу слева не закрывает лицо.

### Durable fix needed before next run
- Для ленты без уменьшения нужен исходник не меньше 1280×720.

### Suggested files to inspect/change
- `memory/runs/R-daytest-1738/design.json`
- `memory/runs/R-daytest-1738/designed.jpg`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- Холст уменьшен по правилу макета: исходник 1200×630 меньше окна, фото не растягивал. Для ленты без уменьшения нужен исходник не меньше 1280×720.

## INC-20261022-1807-fn-ads-other
status: needs-human
run_date: 2026-10-22
role: fn-ads
run_id: R-daytest-1807
severity: low
category: other

### What went wrong
- Дневной тест: рекламу не читали, слоты пустые, пост уходит сразу.

### How the agent recovered this run
- plan_slot по пустой сетке

### Durable fix needed before next run
- Вернуть чтение канала рекламы после тестового дня

### Suggested files to inspect/change
- `none`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- Пустой список — приказ дневного теста. Логику рекламы в коде не выключал и не вырезал. После тестового дня снова читать канал рекламы.

## INC-20261022-1820-fn-emoji-catalog
status: needs-human
run_date: 2026-10-22
role: fn-emoji
run_id: R-daytest-1807
severity: low
category: catalog

### What went wrong
- В каталоге нет custom emoji с тегом nottingham: значка «Ноттингем Форест» нет, keywords у всех items пустые. Тегов chelsea, crystal-palace, palace и premier-league тоже нет.

### How the agent recovered this run
- В заголовок поставлен мяч из futbol_icon: id 5377435673206730908, fallback ⚽️, тег football. Набор futbol_klub и чужие клубы не ставились. Абзац без emoji: то же о старте сезона, не отдельная цитата, не травма и не трансфер.

### Durable fix needed before next run
- Проставить keywords клубов при sync emoji и добавить в каталог значок Nottingham Forest с тегом nottingham.

### Suggested files to inspect/change
- `shared/emoji-catalog.json`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- В каталоге нет тега nottingham, keywords пустые. Тегов chelsea, crystal-palace, palace и premier-league тоже нет. Id не сочинялись.

## INC-20261022-1826-fn-design-other
status: needs-human
run_date: 2026-10-22
role: fn-design
run_id: R-daytest-1807
severity: low
category: other

### What went wrong
- Исходник 460x368 меньше ленты, холст уменьшен без растягивания

### How the agent recovered this run
- compose уменьшил холст

### Durable fix needed before next run
- Брать исходник не меньше окна выбранного размера

### Suggested files to inspect/change
- `none`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- Нижний предел холста 640×360 в branding.py уже снят. Исходник 460×368 не растягивался: холст уменьшен. Предел не возвращал, код не менял. Для ленты без уменьшения нужен исходник не меньше окна.

## INC-20261022-1837-fn-ads-other
status: needs-human
run_date: 2026-10-22
role: fn-ads
run_id: R-daytest-1837
severity: low
category: other

### What went wrong
- Дневной тест: рекламу не читали, слоты пустые, пост уходит сразу.

### How the agent recovered this run
- plan_slot по пустой сетке

### Durable fix needed before next run
- Вернуть чтение канала рекламы после тестового дня

### Suggested files to inspect/change
- `none`

### Secrets
- none recorded

### Fixer resolution
- needs-human
- Пустой список — приказ дневного теста. Логику рекламы в коде не выключал и не вырезал. После тестового дня снова читать канал рекламы.

## INC-20261022-2057-fn-design-design
status: fixed
run_date: 2026-10-22
role: fn-design
run_id: R-20261022-203421
severity: medium
category: design

### What went wrong
- Первая генерация main поставила чужой бейдж «СРОЧНО». Повтор с тем же шаблоном main дал жёлтый бейдж «НОВОСТЬ». Task id первой: 9190e6883770da4d6c7825ca27d9177a. Task id оставленной: 26d7fd19d3ee6237f1c07e578fa0f9c6.

### How the agent recovered this run
- Оставлен второй кадр 600×600: один логотип FC, подпись GOL88.RU, текст рейтинга по-русски, Кейн в центре, без просмотров, даты и времени.

### Durable fix needed before next run
- В промпте main явно запретить бейдж «СРОЧНО» и требовать только «НОВОСТЬ», чтобы модель не копировала срочный пример с контент-борда.

### Suggested files to inspect/change
- `memory/runs/R-20261022-203421/designed.jpg`
- `memory/runs/R-20261022-203421/design.json`
- `src/newsagent/flux.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- В промпте шаблона main бейдж только «НОВОСТЬ». Бейдж «СРОЧНО» запрещён, чтобы модель не копировала срочный пример с контент-борда. Шаблон urgent эту строку не получает.

## INC-20261022-2107-fn-emoji-other
status: fixed
run_date: 2026-10-22
role: fn-emoji
run_id: R-20261022-203421
severity: low
category: other

### What went wrong
- Значок обычной новости помечался тегом main, и проверка сюжета его отклоняла.

### How the agent recovered this run
- yes

### Durable fix needed before next run
- Тег шаблона main теперь пишется как news.

### Suggested files to inspect/change
- `src/newsagent/custom_emoji.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- Тег шаблона main в TOPIC_GATE уже пишется как news. Тест tests/test_custom_emoji.py это покрывает. Правку не откатывал.

## INC-20261022-2158-fn-design-design
status: fixed
run_date: 2026-10-22
role: fn-design
run_id: R-20261022-213653
severity: medium
category: design

### What went wrong
- Первый compose взял шаблон transfer, потому что в story.action стоит transfer. Сделки и суммы нет: ПСЖ доволен Сафоновым и зимой нового вратаря не ищет.

### How the agent recovered this run
- В design.json записан template main, карточка собрана повторно один раз. На кадре бейдж НОВОСТЬ, заголовок дословно, один логотип FC, GOL88.RU, 600x600, Nano Banana 2.1, 1K.

### Durable fix needed before next run
- pick_template не должен ставить transfer без сделки и суммы, если сюжет — отказ искать или покупать игрока.

### Suggested files to inspect/change
- `memory/runs/R-20261022-213653/design.json`
- `memory/runs/R-20261022-213653/designed.jpg`
- `src/newsagent/branding.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- pick_template оставляет шаблон main, если сюжет — отказ искать или покупать игрока и в тексте нет суммы или уже согласованной сделки. Шаблон transfer и гербы клубов не откатывались.

## INC-20261022-2209-fn-copy-other
status: fixed
run_date: 2026-10-22
role: fn-copy
run_id: R-20261022-213653
severity: low
category: other

### What went wrong
- Заголовок закрыл весь текст, а проверка требует жирный факт в абзаце.

### How the agent recovered this run
- yes

### Durable fix needed before next run
- В абзац вынесены покупка вратаря и слухи из summary.

### Suggested files to inspect/change
- `memory/runs/R-20261022-213653/copy.json`

### Secrets
- none recorded

### Fixer resolution
- fixed
- Если заголовок закрыл текст, факт из summary, которого нет в заголовке, становится абзацем. Жирным берётся цифра, имя или короткая оговорка из этого абзаца. Пост из одного заголовка больше не требует жирный факт в пустом абзаце.

## INC-20261022-2308-fn-scout-script
status: fixed
run_date: 2026-10-22
role: fn-scout
run_id: R-20261022-225941
severity: low
category: script

### What went wrong
- Фильтр оставил в топ-8 сюжет Формулы-1 (Шумахер, раздел auto) и почтовую рассылку Guardian Football Daily.

### How the agent recovered this run
- да, оба пункта убраны из candidates.json, осталось 6 сюжетов мирового футбола

### Durable fix needed before next run
- Отсекать другой вид спорта даже при упоминании иностранного клуба, если URL или текст про авто/формулу. Не брать email-дайджесты вроде Football Daily.

### Suggested files to inspect/change
- `memory/runs/R-20261022-225941/candidates.json`
- `src/newsagent/lexicon.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- Формула, Formula 1 и раздел /auto/ отсекаются даже если в тексте есть иностранный клуб. Рассылка Football Daily и email digest тоже не попадают в кандидаты. Обычный матч остаётся.

## INC-20261022-2315-fn-memory-script
status: fixed
run_date: 2026-10-22
role: fn-memory
run_id: R-20261022-225941
severity: medium
category: script

### What went wrong
- pick_story счёл новым разбор преемников Кэррика в «Манчестер Юнайтед» (Guardian, slug michael-carrick, клубы man-utd и como, action sack). За этот день уже есть sent: Carrick hits back after Como rout (result, como+man-utd) и «МЮ» не уволит Кэррика, смотрят Нагельсманна (sack, man-utd). Фамилии Кэррик в заголовке нет, остовы вышли кнтндрс/мн/нкст, похожесть с сюжетом про Комо 0.31, event_key другой из-за лишних клубов, поэтому ни title, ни player, ни match не сработали.

### How the agent recovered this run
- URL Guardian записан в exclude.json, pick_story запущен снова, код 0. Выбран новый сюжет: «ПСЖ» нацелен подписать вингера «Байера» на замену травмированному Кварацхелии (news-6668464). Отсечены выходной «МЮ» после «Комо» (match) и колонка про Фернандеша (player). Сафонов news-6668364 и кража у Фернандеша ниже по score и до выбора не дошли: это точный URL и тот же игрок в тот же день.

### Durable fix needed before next run
- Брать фамилии не только из заголовка, но и из slug URL (michael-carrick). Тот же клуб и тот же игрок в тот же день считать дублем, даже если в заголовке фамилии нет.

### Suggested files to inspect/change
- `src/newsagent/memory.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- Фамилия из пары имя-фамилия в slug URL (michael-carrick) участвует в сверке. Тот же клуб и тот же игрок в тот же день — дубль, даже если в заголовке фамилии нет. Короткий список без фамилии в адресе не отсекается.

## INC-20261022-2328-fn-design-api
status: fixed
run_date: 2026-10-22
role: fn-design
run_id: R-20261022-225941
severity: medium
category: api

### What went wrong
- Kie не собрал карточку: generate task timeout. Скрипт собрал Pillow, шаблон urgent, бейдж СРОЧНО, файл 600x600.

### How the agent recovered this run
- Карточка designed.jpg собрана Pillow с photo.jpg: герой Ибрахим Маза, заголовок дословно, один логотип FC, без просмотров, даты и времени. Подпись внизу — источник championat, не GOL88.RU, потому что Nano Banana не ответил.

### Durable fix needed before next run
- Разобрать таймаут задачи Kie. Пока модель недоступна, запасной Pillow должен ставить GOL88.RU, а не source_id.

### Suggested files to inspect/change
- `memory/runs/R-20261022-225941/design.json`
- `memory/runs/R-20261022-225941/designed.jpg`
- `src/newsagent/flux.py`
- `scripts/compose_photo.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- Запасной Pillow ставит подпись GOL88.RU, а не source_id.

## INC-20261022-2331-fn-design-api
status: fixed
run_date: 2026-10-22
role: fn-design
run_id: R-20261022-225941
severity: medium
category: api

### What went wrong
- Первый прогон Kie завершился generate task timeout, карточка ушла в Pillow. Повтор с --force нужен из-за этого таймаута.

### How the agent recovered this run
- да: повтор собрал nano-banana-2-1, status ok, 600x600, шаблон urgent, бейдж СРОЧНО, GOL88.RU, один логотип FC.

### Durable fix needed before next run
- Разобрать таймаут задачи Kie, чтобы первый прогон не падал в Pillow.

### Suggested files to inspect/change
- `memory/runs/R-20261022-225941/design.json`
- `memory/runs/R-20261022-225941/designed.jpg`
- `src/newsagent/flux.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- Если Kie оборвал задачу по таймауту, сборка карточки повторяется один раз до запасного Pillow. Другие ошибки по-прежнему сразу уходят в Pillow.

## INC-20261023-0737-fn-scout-script
status: fixed
run_date: 2026-10-23
role: fn-scout
run_id: R-20261023-072810
severity: low
category: script

### What went wrong
- Лента sportsru заполнила candidates.json пятью видеодайджестами video.sports.ru и женским КЧМ-2028.

### How the agent recovered this run
- Видеодайджесты и нецелевые темы отсеяны, в candidates.json отобраны 6 чистых сюжетов мирового футбола.

### Durable fix needed before next run
- Отсекать ссылки video.sports.ru и видеодайджесты в feeds.py, чтобы они не вытесняли текстовые новости.

### Suggested files to inspect/change
- `memory/runs/R-20261023-072810/candidates.json`
- `src/newsagent/feeds.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- В SKIP_URL в feeds.py добавлены video.sports.ru и sports.ru/video/, добавлен фильтр VIDEO_DIGEST для заголовков и описаний, в lexicon.py паттерн _DIGEST дополнен видеодайджестами.

## INC-20261023-0747-fn-photo-script
status: fixed
run_date: 2026-10-23
role: fn-photo
run_id: R-20261023-072810
severity: medium
category: script

### What went wrong
- fetch_photo.py скачал плашку ESPN stitcher с логотипами клубов вместо фото героя

### How the agent recovered this run
- Удалил photo.png, добавил URL в exclude.json для повтора memory -> photo

### Durable fix needed before next run
- Добавить stitcher в bad_url в src/newsagent/photos.py

### Suggested files to inspect/change
- `src/newsagent/photos.py`

### Secrets
- none recorded

### Fixer resolution
- fixed
- Паттерн BAD_URL в src/newsagent/photos.py дополнен токеном stitcher, отсекающим служебные коллажи ESPN.

## INC-20261102-1840-fn-critic-other
status: open
run_date: 2026-11-02
role: fn-critic
run_id: R-20261102-183808
severity: medium
category: other

### What went wrong
- REWORK fn-design: реклама GOL88.RU и брак ноги на карточке

### How the agent recovered this run
- no

### Durable fix needed before next run
- Пересобрать карточку без чужого лого и артефактов

### Suggested files to inspect/change
- `designed.jpg`
- `design.json`

### Secrets
- none recorded

### Fixer resolution
- pending

## INC-20261102-1841-fn-design-other
status: open
run_date: 2026-11-02
role: fn-design
run_id: R-20261102-183808
severity: medium
category: other

### What went wrong
- REWORK критика: На карточке внизу чужой бренд GOL88.RU — убрать водяной знак/логотип, без рекламы на фото.; На ноге Олисе видны артефакты генерации (деформация голени/стопы) — другой кадр или перегенерация без брака.; В начале заголовка поста — два герба клубов «Атлетико» и «Бавария», не флаги 🇪🇸/🇩🇪 (если правится текст/emoji — через produce).

### How the agent recovered this run
- карточка пересобрана

### Durable fix needed before next run
- разобрать фиксеру

### Suggested files to inspect/change
- `none`

### Secrets
- none recorded

### Fixer resolution
- pending

## INC-20261103-1052-fn-publish-other
status: fixed
run_date: 2026-11-03
role: fn-publish
run_id: R-20261103-103915
severity: medium
category: other

### What went wrong
- публикация: Server closed the connection: 146 bytes read on a total of 1347703872 expected bytes

### How the agent recovered this run
- не указано

### Durable fix needed before next run
- разобрать фиксеру

### Suggested files to inspect/change
- `none`

### Secrets
- none recorded

### Fixer resolution
- fixed
- `publish.py` повторяет sendPhoto/send_file до трёх раз при обрыве соединения, IncompleteRead и сетевых сбоях Telegram, с паузой между попытками. Пост R-20261103-103915 ушёл с message_id=296 после повтора вне скрипта.
