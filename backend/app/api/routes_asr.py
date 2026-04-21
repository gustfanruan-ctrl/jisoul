import asyncio
import json
from contextlib import suppress

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
import websockets

from app.config import settings
from app.models.schemas import ASRTokenResponse

router = APIRouter()


@router.get("/token", response_model=ASRTokenResponse, summary="获取 ASR 鉴权信息")
async def get_asr_token():
    if not settings.DASHSCOPE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="DASHSCOPE_API_KEY 未配置，请在环境变量或 .env 中设置",
        )

    return ASRTokenResponse(
        api_key=settings.DASHSCOPE_API_KEY,
        ws_url=settings.ASR_WS_URL,
        model=settings.ASR_MODEL,
    )


@router.websocket("/ws")
async def asr_ws_proxy(client_ws: WebSocket):
    await client_ws.accept()

    if not settings.DASHSCOPE_API_KEY:
        await client_ws.send_text(json.dumps({
            "type": "error",
            "error": {"message": "DASHSCOPE_API_KEY 未配置"},
        }))
        await client_ws.close()
        return

    model = client_ws.query_params.get("model") or settings.ASR_MODEL
    ws_url = client_ws.query_params.get("ws_url") or settings.ASR_WS_URL
    if not ws_url.startswith("wss://dashscope.aliyuncs.com/") and not ws_url.startswith("wss://dashscope-intl.aliyuncs.com/"):
        await client_ws.send_text(json.dumps({
            "type": "error",
            "error": {"message": "非法 ASR WS 地址"},
        }))
        await client_ws.close()
        return

    remote_url = f"{ws_url}?model={model}"
    remote_headers = {"Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}"}

    try:
        async with websockets.connect(
            remote_url,
            additional_headers=remote_headers,
            ping_interval=20,
            ping_timeout=20,
            max_size=8 * 1024 * 1024,
        ) as remote_ws:
            async def forward_client_to_remote():
                while True:
                    msg = await client_ws.receive_text()
                    await remote_ws.send(msg)

            async def forward_remote_to_client():
                async for msg in remote_ws:
                    await client_ws.send_text(msg if isinstance(msg, str) else msg.decode("utf-8"))

            t1 = asyncio.create_task(forward_client_to_remote())
            t2 = asyncio.create_task(forward_remote_to_client())
            done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_EXCEPTION)
            for t in pending:
                t.cancel()
                with suppress(asyncio.CancelledError):
                    await t
            for t in done:
                exc = t.exception()
                if exc:
                    raise exc
    except WebSocketDisconnect:
        pass
    except Exception as e:
        with suppress(Exception):
            await client_ws.send_text(json.dumps({
                "type": "error",
                "error": {"message": f"ASR 代理连接失败: {e}"},
            }))
    finally:
        with suppress(Exception):
            await client_ws.close()
