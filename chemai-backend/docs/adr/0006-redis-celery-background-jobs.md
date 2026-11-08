# Background jobs move to Redis + Celery

ChemAI's post-practice barrier diagnosis ran inside a `daemon` thread spawned from the request handler, so it was lost on restart and had no retry; notification delivery and memory-append were fire-and-forget and non-idempotent. We decided to introduce Redis as a durable job broker with Celery workers for the non-OCR background jobs, reuse that same Redis for shared rate-limiting/cache, and make every job consumer idempotent. Kafka was rejected: on a single-node, single-process deployment its partitioning/replay/throughput buy nothing while its operational cost is real.

Status: accepted

## Considered Options

- **Kafka**: rejected — partitioning, strict ordering, replay, and multi-consumer fan-out are all unused on a single node; adds KRaft/Zookeeper operations for no benefit.
- **Extend the existing APScheduler + `ocr_tasks` task-table pattern** (a DB-outbox style queue): the incumbent OCR path already works this way, so this is the obvious "no new infra" choice. Rejected as the general mechanism because the in-process APScheduler job store is not durable/retryable across restart, and it does not give us the shared cache and rate-limit that Redis does.
- **Redis Streams / arq (no Celery)**: a lighter, async-native alternative. Acceptable; Celery was chosen for maturity, built-in retries and visibility, and ecosystem.
- **Celery + Redis (chosen)**: Redis as broker (AOF enabled for restart durability) plus cache/rate-limit reuse.

## Consequences

- Consumers must tolerate at-least-once delivery:
  1. Notification delivery needs a dedup key checked before send (today `DiscordGateway.send` / `EmailGateway.send` fire unconditionally).
  2. Memory-append (`practice_history`, `barrier_history` via `append=True`) must dedup by `exam_record_id` / diagnosis event — the current bare append double-records on retry.
  3. Barrier diagnosis is already idempotent (`run_llm_barrier_diagnosis` re-aggregates `Student.barrier_type` rather than incrementing), so it only needs retry.
- The existing APScheduler OCR task-table path stays; consolidating it onto the queue is a separate, later decision.
- **No-Redis fallback**: `enqueue_job` degrades to running the handler synchronously when the broker is unreachable (`kombu`/`redis`/`amqp` connection errors), so an undeployed or down Redis does not break the request path; the queue kicks in automatically once Redis and a worker are up.
