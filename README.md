# block_lag_exporter
Simple metrics exporter to export latest block lag for evm-based chains. It exports 2 metrics:
* `head_lag_seconds` - histogram with values from uptime
* `head_lag_seconds_last` - gauge with latest value of block lag

and 2 endpoints on `http://0.0.0.0:${LISTENER_PORT}`:
* `/metrics` - to scrape prometheus metrics
* `/health` - to check liveness 

Sub-second block timestamps are used when the chain provides them:
* the `timestampMs` header field (Base, 200ms blocks)
* the millisecond part in `mixHash` ([BEP-520](https://github.com/bnb-chain/BEPs/blob/master/BEPs/BEP-520.md), BSC)

Otherwise the whole-second `timestamp` is used.

Default values are optimized to use it as a k8s geth/geth-like sidecar 
Use following environment variables to override defaults:
* `LISTENER_PORT=8000` - port to listen 
* `WS_URL=ws://localhost:8545` - websocket URL to connect and subscribe to new blocks
* `WS_READ_TIMEOUT=25` - websocket timeout to wait for new blocks data
* `HIST_BUCKETS=0.05,0.08,0.1,0.15,0.2,0.3,0.4,0.6,0.8,1.0,1.2,1.6,2.0,2.5,3.0,4.0,8.0,+Inf` - override prometheus 
histogram buckets for histogram metric
* `MAX_BLOCK_LAG=60.0` - all data above this threshold will be logged, but not added to metrics. This exporter is intended to monitor  
 the current block lag instead of initial sync-up/catch-up. 
