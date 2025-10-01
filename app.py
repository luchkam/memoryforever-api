import os
import json
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse

app = FastAPI(title="MemoryForever API")

WEBHOOK_TOKEN = os.getenv("TOCHKA_WEBHOOK_TOKEN", "changeme")

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/ok")
async def ok_page():
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'>"
        "<h1>Оплата принята ✅</h1><p>Можно вернуться в Telegram.</p>"
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
