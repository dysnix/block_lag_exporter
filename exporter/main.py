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
from prometheus_client import Histogram, Gauge, CollectorRegistry


async def server_stats(request: web.Request) -> web.Response:
    """
    It's a copy from prometheus_async, using custom registry
    Return a web response with the plain text version of the metrics.

    :rtype: :class:`aiohttp.web.Response`
    """
    generate, content_type = aio.web._choose_generator(request.headers.get("Accept"))

    rsp = web.Response(body=generate(registry))
    # This is set separately because aiohttp complains about `;` in
    # content_type thinking it means there's also a charset.
    # cf. https://github.com/aio-libs/aiohttp/issues/2197
    rsp.content_type = content_type

    return rsp


def process_block(block):
    timestamp = int(block['timestamp'], 16)
    block_number = int(block['number'], 16)
    ts = time.time()
    lag = ts - timestamp
    miner = block['miner']
    gasUsed = int(block['gasUsed'], 16)
    gasLimit = int(block['gasLimit'], 16)
    gasUsedPct = float(gasUsed * 100 / gasLimit)
    if lag < max_block_lag:
        hist.observe(lag)
        hist_miner.labels(miner=miner).observe(lag)
        gauge.set("{:+.4f}".format(lag))
    # print(block, flush=True)
    print(
        "ts=%d block=%d lag=%2.4f miner=%s gasUsed=%2.1f%% (%d/%d)" % (timestamp, block_number, lag, miner, gasUsedPct,
                                                                       gasUsed, gasLimit), flush=True)
    return


async def get_event():
    try:
        async with connect(ws_url) as ws:
            await ws.send('{"jsonrpc": "2.0", "id": 1, "method": "eth_subscribe", "params": ["newHeads"]}')
            subscription_response = await ws.recv()
            print("ws subscription: %s" % subscription_response, flush=True)
            while True:
                message = await asyncio.wait_for(ws.recv(), timeout=5)
                response = json.loads(message)
                block = response['params']['result']
                process_block(block)
    except Exception as e:
        print(e, flush=True)
        return


async def event_wrapper():
    # await asyncio.sleep(0)
    counter = 0
    while True:
        print("Starting wrapper tasks #%d" % counter, flush=True)
        await get_event()
        print("await app done", flush=True)
        await asyncio.sleep(2)
        counter += 1
    # yield


async def background_tasks(app):
    app[ws_listener] = asyncio.create_task(event_wrapper())
    yield
    app[ws_listener].cancel()
    await app[ws_listener]


async def on_shutdown(app: web.Application) -> None:
    print("Shutting down ...", flush=True)
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
    max_block_lag = float(os.environ.get("MAX_BLOCK_LAG", 60.0))

    registry = CollectorRegistry(auto_describe=True)

    hist = Histogram('head_lag_seconds', 'Last block lag',
                     buckets=buckets.split(','))
    hist_miner = Histogram('head_lag_miners', 'Last block lag per miner',
                           buckets=buckets.split(','), labelnames=["miner"], registry=registry)
    gauge = Gauge('head_lag_seconds_last', 'Last block lag')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = web.Application()
    ws_listener = web.AppKey("ws_listener", asyncio.Task[None])
    app.cleanup_ctx.append(background_tasks)
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/metrics", aio.web.server_stats)
    app.router.add_get("/metrics/miner", server_stats)
    app.router.add_get("/health", health)

    web.run_app(app, port=metrics_port, loop=loop, handle_signals=True)
