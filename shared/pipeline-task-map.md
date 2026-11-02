# Карта выпуска

| Шаг | Кто | Что внутри | Артефакты | Дальше только если |
|-----|-----|------------|-----------|--------------------|
| gate | `pipeline.py gate` | doctor, start_run, fetch_ads, plan_slot | `context.json`, `ads.json`, `slot-plan.json` | `prepare=true` (иначе run удаляется) |
| scout | `pipeline.py scout` | lock_slot, fetch_news, pick_story | `candidates.json`, `story.json`, `memory-decision.json` | слот свободен, есть неопубликованная новость дня |
| produce | `pipeline.py produce` | write_copy, place_emoji, write_voice, render_caption ‖ fetch_photo, compose_photo, review_photo, validate_post | `copy.json`, `emoji.json`, `voice.json`, `caption.html`, `design.json`, `photo-review.json`, `machine.json` | machine PASS |
| copy | Task `fn-copy` | только при коде 3 (Gemini упал), затем `after_copy` | `copy.json` engine=cursor | — |
| critic | Task `fn-critic` | смысл, фото, гербы | `critic.json` | PASS (REWORK → `pipeline.py rework`, до 2 раз) |
| publish | `pipeline.py publish` | validate --require-critic, publish | `publish-result.json` | — |
| finish | `pipeline.py finish` | collect_difficulties, optimize_pipeline, prune_runs | `fixer-brief.md` | `fixer=needed` → Task `fn-fixer` |
