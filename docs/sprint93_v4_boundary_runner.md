# Sprint 93.2B V4 boundary runner — review candidate, not activated

## Current status

V4 includes bounded paired acquisition, a separate recovery-only lifecycle
manager, and a fresh-start continuous supervisor. There is **no V4 activation manifest**
and no authorization to substitute a V1/V2/V3 manifest. Do not merge this change
as a claim that the unattended 45-day experiment is operationally ready.
No real market data was used to develop or test this change.

The original CLI performed public GitHub verification immediately before a live
snapshot. Observed verification durations were 39.615, 42.502 and 46.235 seconds.
The 6.620-second observed spread exceeds the unchanged two-second entry window.
Starting that CLI a fixed number of seconds early is therefore not dependable.

## Bounded command

`collect-pair-at-boundary` performs public verification once in memory, acquires
one writer lease, waits until activation before MT5 setup, initializes MT5 once,
selects both frozen symbols, and waits for an **explicit entry-bar UTC boundary**.
It checks local frozen bytes again before acquisition; there is no network
verification in the entry window. It captures BTCUSD and ETHUSD sequentially
through the same MT5 connection, then validates **both** snapshots before any
decision/evidence write. This does not claim simultaneous tick acquisition.

The requested entry bar must be M15-aligned, strictly before the exclusive end,
and at least one full M15 interval after the first eligible signal-bar open.
For example, an eligible signal candle opening at 21:30 UTC becomes complete at
21:45 UTC; 21:45 is the requested entry boundary, not 21:31. These example times
are explanatory only and are not a new activation schedule.

Public verification and MT5 setup must finish at least ten seconds before the
requested boundary. A missed preparation/acquisition/entry deadline fails closed.
The runner never shifts its target, backdates a snapshot, changes the two-second
rule, retries using different live prices, or discards partial evidence.

All mutating CLI commands share a separate cross-process runner lease. The
existing journal transaction locks are retained. Direct library use outside the
CLI must not run concurrently with this command.

Existing open virtual positions or unresolved entry intents block this bounded
command: it must not wait unattended while an existing lifecycle needs attention.
If the new cycle opens a position, a lifecycle supervisor must subsequently
manage it. The returned `lifecycle_supervisor_running` value is explicitly false.

The command needs the existing published-manifest arguments plus
`--entry-bar-open-utc`. Do not construct a live command with guessed PR numbers,
commit SHAs or times. These values must come from the eventual reviewed V4
activation and manifest-publication PRs.

## Tests and acceptance limits

Tests use synthetic candles, a fake clock and fake MT5 transport. They cover:

- the three observed network delays, all absorbed before the target boundary;
- no pre-activation MT5 setup/capture;
- late startup, slow setup, stale candles, clock steps and slow acquisition;
- both symbols acquired and checked before the first write;
- source/manifest/runtime changes after public verification;
- incompatible broker contexts and the single-writer lease;
- retained partial evidence and explicit failure on a late durable entry;
- one MT5 initialization/shutdown, including setup failures;
- real strategy/journal integration on synthetic no-trade candles.

Synthetic timing is not a live latency guarantee. In particular, real strategy
signals can invoke valuation/risk metadata work and durable writes. The original
entry deadline remains checked inside the durable-entry path; passing acquisition
alone must never be presented as a successful entry cycle.

## Existing-lifecycle recovery command

`manage-existing-lifecycles` uses the published-manifest arguments, performs public
verification once, owns the same writer lease, and uses one read-only MT5 session.
It refuses to start before activation. It does **not** run alongside the bounded
collector and is **not** the continuous M15 decision scheduler described below.

The coordinator:

- resolves every pending entry using its frozen decision/intent, without taking
  replacement prices; an existing durable entry intent can materialize its
  virtual position under the unchanged core recovery rules;
- replays frozen ordinary or timebox terminal inputs before acquiring new prices;
- checks the current terminal/account identity using metadata only before frozen
  recovery, because recovery itself can invoke read-only risk/valuation APIs;
- finds fully terminal but not-yet-settled pairs, and finalizes each once;
- excludes both-no-trade observations from the evaluation population;
- acquires each outstanding symbol once per poll and validates all acquisitions
  before updating any branch; the recorded decision's server/currency/build must
  still match, and both current symbol contexts must agree;
- polls existing positions with a one-second target cadence and fails on clock
  steps, excessive gaps, or acquisition/write cycles exceeding five seconds;
- records final-bar boundary authority before ordinary updates, and after the
  exclusive end uses only the exact completed candle bound to that authority;
- skips already-terminal branches, and fails if final-bar authority or the exact
  final candle is unavailable. It never fabricates missing authority after end.

The cadence and five-second failure threshold are operational review candidates,
not a change to the **two-second entry deadline**, nor a guarantee that all market
ticks are observed. Long broker calls cannot be preempted by this synchronous
loop; an overrun is detected when the call returns. The command stops when all
existing lifecycles are settled/excluded, or fails while preserving partial data.

An adjacent append-only `paired_evidence.jsonl.lifecycle.jsonl` operational journal
records start, failure/completion and at most one checkpoint per M15 interval.
Every record labels experiment continuity **UNVERIFIED**. A crash can leave an
unmatched start; neither a later successful recovery nor a checkpoint certifies
uninterrupted forward evidence. These records are not evaluation observations.

Synthetic tests cover poll/recovery failure paths and real virtual-position,
terminal and settlement journals. They include a simulated crash after a durable
position close but before the paired terminal event, for ordinary and timebox
exits, followed by reconstruction and idempotent recovery. No live data is used.

## Continuous supervisor (review candidate, capacity blocked)

`supervise-forward` performs public verification once, holds one writer lease,
and initializes one MT5 session only after activation. It must be launched before
activation and accepts **no** window, target-bar or cadence overrides. All decision
boundaries come from the verified manifest: start + M15 through end - M15.

At each boundary it acquires/validates both symbols before writing either decision,
commits both frozen entry outcomes, and then applies those same snapshots to the
outstanding virtual lifecycles. Between boundaries it polls outstanding symbols.
Broker identity must remain consistent even across intervals with no open trades.
At the exclusive end it collects no new decision and timeboxes remaining positions
using the existing final-bar-authority rules. Final coverage checks require the
exact expected decision universe, no unresolved entries, and no outstanding trades.

Entry writes take priority over terminal valuation at a decision boundary. The
two-second entry limit and five-second lifecycle limits are not relaxed. Since
broker calls are synchronous, a lifecycle poll that crosses an upcoming boundary
fails rather than being relabeled as a new decision acquisition. Missing a boundary,
an excessive observation gap, clock step or identity change also fails closed.

An adjacent append-only `paired_evidence.jsonl.supervisor.jsonl` journal records
the initial next boundary, each completed boundary and next target, observed-symbol
timestamps, the paired-evidence hash-chain tip, and failure or final completion.
No per-tick audit growth is added. Any existing evidence, operational journal
(including empty/torn files), or orphan virtual-position journal prevents a fresh
run. There is **no automatic resume**, catch-up, target shift or backfill. After a
failure, preserve the journals; recovery-only management remains a separate mode
and cannot certify continuity. A hard process death can leave an unmatched start.

Successful completion returns `FINISHED_PENDING_REVIEW`, not a research-validity
certificate. Review must bind the final operational checkpoint to the final paired
evidence tip before accepting the collection. No real run has been started.

## Measured capacity blocker

The synthetic capacity diagnostic uses real no-trade event shapes, replicated and
rehash-chained in temporary files. The replicated history is a storage workload,
**not** semantically audited research evidence. A new timed pair then uses the real
strategy/collector/durable-entry paths with wall time advancing normally; all MT5
access is explicitly blocked. Results from one local run:

| Historical pairs | Historical JSONL bytes | Timed attempt (seconds) | Durable pair |
| --- | ---: | ---: | --- |
| 0 | 0 | 0.256404 | Completed |
| 64 | 4,535,572 | 3.588793 | Rejected: deadline missed |
| 512 | 36,285,869 | 12.864086 | Rejected: deadline missed |

These are durations until completion/failure, not the time needed to successfully
finish both entries. They exclude live transport, local-freeze and supervisor
checkpoint overhead, so they are not an optimistic end-to-end launch guarantee.
The capacity tests pass when overruns fail closed; a passing test suite therefore
**does not mean the capacity gate passed**. Repeat with:

`python -m pytest -q -s tests/test_sprint93_2b_synthetic_capacity.py`

A separate profiled 64-pair test run (including fixture work and profiling overhead)
made 60 journal `verify` and 98 `_read_events` calls. Journal verification accumulated
3.246 seconds and journal reads 2.485 seconds; these nested timings overlap and
must not be added. Repeated full-file parsing/verification is a demonstrated
bottleneck, not just an untested concern. The frozen journal implementation has
not been modified or bypassed. An integrity-preserving indexed/incremental access
design, including crash/corruption tests and memory-growth limits, needs review
before claiming sustainable capacity. A faster host alone does not remove this
growth pattern.

## Remaining launch gates

1. Resolve the measured journal-capacity blocker without weakening integrity,
   durable-entry deadlines, crash recovery, or the frozen strategy/risk semantics.
   Review the continuous scheduler and its exact priority/gap rules as a whole.
2. Validate end-to-end paired acquisition plus durable entry performance at
   representative 45-day storage and concurrent-open-pair loads, with explicit
   memory limits. Synthetic cadence/clock tests pass, but the capacity diagnostic
   currently fails its operational deadline. Do not access sealed forward outcomes
   as an ad hoc test.
3. Review the complete execution closure and tests before merge. Any further
   execution change belongs in that same review cycle before activation.
4. Only after approval/merge, create and publicly publish a fresh write-once V4
   manifest with a new activation boundary. Preserve all earlier manifests.
5. Deploy exactly one active writer. A Windows VPS can improve uptime but cannot
   by itself satisfy the lifecycle, identity, timing or evidence-integrity gates.

The two preserved Sprint92H14_7 reports must remain untracked and must not be
included in any V4 commit. Production/order APIs remain disabled.
