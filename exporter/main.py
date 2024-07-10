import asyncio
import signal
import json
import sys
import os
import time

from web3 import Web3
from websockets import connect
from aiohttp import web
from prometheus_async import aio
from prometheus_client import Histogram, Gauge


def process_block(block):
    timestamp = int(block['timestamp'], 16)
    block_number = int(block['number'], 16)
    ts = time.time()
    lag = ts - timestamp
    hist.observe(lag)
    gauge.set("{:+.4f}".format(lag))
    print("ts=%d block=%d lag=%2.4f" % (timestamp, block_number, lag))
    return


async def get_event():
    try:
        async with connect(ws_url) as ws:
            await ws.send('{"jsonrpc": "2.0", "id": 1, "method": "eth_subscribe", "params": ["newHeads"]}')
            subscription_response = await ws.recv()
            print("ws subscription: %s" % subscription_response)
            while True:
                message = await asyncio.wait_for(ws.recv(), timeout=5)
                response = json.loads(message)
                block = response['params']['result']
                process_block(block)
    except Exception as e:
        print(e)
        return


async def event_wrapper():
    # await asyncio.sleep(0)
    counter = 0
    while True:
        print("Starting wrapper tasks #%d" % counter)
        await get_event()
        print("await app done")
        await asyncio.sleep(2)
        counter += 1
    # yield


async def background_tasks(app):
    app[ws_listener] = asyncio.create_task(event_wrapper())
    yield
    app[ws_listener].cancel()
    await app[ws_listener]


async def on_shutdown(app: web.Application) -> None:
    print("Shutting down ...")
    # there is no sense to wait, metrics server is stopped anyway
    # await asyncio.sleep(30)
    sys.exit(0)


async def health(self):
    return web.Response(text="OK")


if __name__ == "__main__":
    metrics_port = int(os.environ.get("LISTENER_PORT", 8000))
    ws_url = os.environ.get("WS_URL", "ws://localhost:8545")
    buckets = os.environ.get(
        "HIST_BUCKETS", "0.05,0.08,0.1,0.15,0.2,0.3,0.4,0.6,0.8,1.0,1.2,1.6,2.0,2.5,3.0,4.0,8.0,+Inf")

    hist = Histogram('head_lag_seconds', 'Last block lag',
                     buckets=buckets.split(','))
    gauge = Gauge('head_lag_seconds_last', 'Last block lag')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = web.Application()
    ws_listener = web.AppKey("ws_listener", asyncio.Task[None])
    app.cleanup_ctx.append(background_tasks)
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/metrics", aio.web.server_stats)
    app.router.add_get("/health", health)

    web.run_app(app, port=metrics_port, loop=loop, handle_signals=True)
