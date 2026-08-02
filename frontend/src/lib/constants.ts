// Shared cross-component constants (architecture §7.2 — not hardcoded per
// component).

// architecture §15.1: a position's price is considered stale once it's been
// more than 28 hours since the last successful refresh (automated or manual).
export const STALE_THRESHOLD_MS = 28 * 60 * 60 * 1000;
