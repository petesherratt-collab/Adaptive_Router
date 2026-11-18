# Repair V1: steps that never become code (descriptive)

**Status:** FROZEN 2026-11-18 before any provider call. Reuses V3 jobs.

## Question

In the V3 primary run, plans for `library_loans`, `room_bookings` and
`event_rsvps` kept two or three function steps on the models for all 20 jobs,
which made `library_loans` and `room_bookings` slower than the race. Why, and
does an optional repair attempt fix it?

## Change (`fast_path.py`, `repair_attempts`, default 0)

When a step's blind synthesis attempts are spent and the last candidate failed
only because some stored examples mismatched, one more attempt is allowed. Its
prompt adds up to two of the examples the previous candidate got wrong
(arguments, expected, got) and asks for a corrected general implementation.
The result must still reproduce every stored example. This relaxes the rule
that a code writer never sees examples; it is off unless set.

Shape summaries now record, per plan step, its examples, disagreements,
conflicts, probes and every synthesis attempt with its gate reason, so the
cause of a stuck step can be read from the record.

## Run

`--shapes library_loans,room_bookings,event_rsvps --arms R,C --jobs 20
--set plan_shadow=false --set repair_attempts=1`, drained arrival, other
settings as the V3 primary run. C is compared with R in this run, and with the
V3 primary run's C on the same shapes (descriptive).

Readings: per stuck step, why it was stuck (from the diagnostics); repairs
tried and promoted; plan-served medians against R; any wrong promoted
function. Expected cost about $1.
