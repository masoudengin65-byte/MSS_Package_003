# Sprint 93.2B V4 boundary runner — review candidate, not activated

## Current status

V4 includes bounded paired acquisition and a separate recovery-only lifecycle
manager. There is **no V4 activation manifest**
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
collector and is **not** the missing continuous M15 decision scheduler.

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

## Remaining launch gates

1. Integrate and review a **single continuous scheduler** combining paired M15
   acquisition and lifecycle polling under one lease/session, with durable
   missed-boundary/continuity handling. The recovery-only command cannot be chained
   to the bounded collector as a substitute: positions may remain open for many
   boundaries and recovery deliberately does not certify experiment continuity.
2. Validate scheduler/clock behavior and both-symbol acquisition plus durable
   entry performance, including realistic growing journals and simultaneous open
   pairs. Current collector operations reread/verify their journals; short synthetic
   runs are not evidence of 45-day capacity. Do not access sealed forward outcomes
   as an ad hoc test.
3. Review the complete execution closure and tests before merge. Any further
   execution change belongs in that same review cycle before activation.
4. Only after approval/merge, create and publicly publish a fresh write-once V4
   manifest with a new activation boundary. Preserve all earlier manifests.
5. Deploy exactly one active writer. A Windows VPS can improve uptime but cannot
   by itself satisfy the lifecycle, identity, timing or evidence-integrity gates.

The two preserved Sprint92H14_7 reports must remain untracked and must not be
included in any V4 commit. Production/order APIs remain disabled.
