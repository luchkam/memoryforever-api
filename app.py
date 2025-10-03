import os
import json
import logging
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse

app = FastAPI(title="MemoryForever API")

WEBHOOK_TOKEN = os.getenv("TOCHKA_WEBHOOK_TOKEN", "changeme")
TG_BOT_USERNAME = os.getenv("TG_BOT_USERNAME", "").strip().lstrip("@")
TG_START_OK = os.getenv("TG_START_OK", "").strip()
TG_START_FAIL = os.getenv("TG_START_FAIL", "").strip()

def _build_start_param(default_env: str, start_qs: Optional[str], op_id: Optional[str]) -> Optional[str]:
    """
    Выбираем start-параметр в приоритете: ?start=... → ENV → None.
    Если есть op_id, аккуратно добавим его хвостом.
    """
    base = (start_qs or default_env or "").strip()
    if not base:
        return None
    if op_id:
        # безопасно добавим op_id (например: paid_op_123)
        return f"{base}_op_{op_id}"
    return base

def _render_return_page(title: str, subtitle: str, ok: bool, start_param: Optional[str]) -> HTMLResponse:
    """
    Рисуем HTML со стилем, кнопкой возврата в Telegram и автопереходом.
    Если TG_BOT_USERNAME не задан — просто показываем страницу без кнопки/редиректа.
    """
    has_bot = bool(TG_BOT_USERNAME)
    if has_bot:
        # Соберём tg:// и https:// диплинки
        if start_param:
            tg_deep = f"tg://resolve?domain={TG_BOT_USERNAME}&start={start_param}"
            tg_http = f"https://t.me/{TG_BOT_USERNAME}?start={start_param}"
        else:
            tg_deep = f"tg://resolve?domain={TG_BOT_USERNAME}"
            tg_http = f"https://t.me/{TG_BOT_USERNAME}"
    else:
        tg_deep = tg_http = ""

    color = "#16a34a" if ok else "#dc2626"  # зелёный/красный
    icon = "✅" if ok else "❌"

    html = f"""<!doctype html>
<html lang="ru">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, Arial, sans-serif;
    background: #0b0f14; color: #e5e7eb; margin: 0; padding: 0;
    display: grid; place-items: center; min-height: 100dvh;
  }}
  .card {{
    width: min(560px, 92vw);
    background: #111827; border: 1px solid #1f2937;
    border-radius: 16px; padding: 28px; text-align: center;
    box-shadow: 0 10px 30px rgba(0,0,0,0.4);
  }}
  h1 {{ margin: 0 0 8px; font-size: 22px; color: {color}; }}
  p  {{ margin: 0 0 18px; color: #cbd5e1; line-height: 1.4; }}
  .btn {{
    display: inline-block; padding: 12px 16px; border-radius: 10px;
    text-decoration: none; background: {color}; color: white; font-weight: 600;
  }}
  .muted {{ font-size: 13px; color: #94a3b8; margin-top: 12px; }}
</style>
<div class="card">
  <h1>{icon} {title}</h1>
  <p>{subtitle}</p>
  {f'<a class="btn" href="{tg_http}" id="backBtn" rel="noopener">Открыть бота в Telegram</a>' if has_bot else ''}
  <div class="muted">Можно закрыть эту вкладку после возврата.</div>
</div>
{"<script>const deepLink="+json.dumps(tg_deep)+";const webLink="+json.dumps(tg_http)+";setTimeout(()=>{try{window.location.href=deepLink;}catch(e){} setTimeout(()=>{try{window.location.href=webLink;}catch(e){}},800);},1200);</script>" if has_bot else ""}
"""

    return HTMLResponse(html)

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/ok")
async def ok_page(start: Optional[str] = None, op_id: Optional[str] = None):
    start_param = _build_start_param(TG_START_OK, start, op_id)
    return _render_return_page(
        title="Оплата принята",
        subtitle="Спасибо! Можно вернуться в Telegram для продолжения.",
        ok=True,
        start_param=start_param,
    )

@app.get("/fail")
async def fail_page(start: Optional[str] = None, op_id: Optional[str] = None):
    start_param = _build_start_param(TG_START_FAIL, start, op_id)
    return _render_return_page(
        title="Оплата не прошла",
        subtitle="Платёж не был завершён или отклонён. Вернитесь в Telegram, чтобы попробовать снова.",
        ok=False,
        start_param=start_param,
    )

@app.post("/payments/tochka/webhook/{token}")
async def tochka_webhook(token: str, request: Request):
    # Простейшая защита: секрет в URL
    if token != WEBHOOK_TOKEN:
        raise HTTPException(status_code=403, detail="bad token")

    # Тело может быть JSON; логируем целиком
    try:
        body = await request.json()
    except Exception:
        raw = await request.body()
        body = {"_raw": raw.decode("utf-8", "ignore")}

    # Мягко вытащим “идентификаторы”, если есть
    event_id = (
        body.get("id")
        or body.get("eventId")
        or body.get("operationId")
        or body.get("qrId")
    )
    event_type = body.get("type") or body.get("event") or body.get("eventType")

    logging.info("[TOCHKA WEBHOOK] type=%s id=%s body=%s",
                 event_type, event_id, json.dumps(body, ensure_ascii=False))

    # TODO: здесь позже отметим заказ как 'paid'
    return JSONResponse({"ok": True})
