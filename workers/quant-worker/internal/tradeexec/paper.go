package tradeexec

import "os"

// Paper semantics (verified against current Python, 2026-09):
//
// LONGPORT_PAPERTRADING, require_paper, and submit_order_async(allow_sim=...)
// were removed. The platform no longer intercepts orders with a paper gate.
// Whatever Longbridge account is stored in quant_longbridge_config is what
// receives the order (paper account token → paper fills; live token → live).
//
// Safety defaults this Go path still enforces:
//   - auto_trade_enabled defaults to off; jobs only submit when that flag is on
//   - trade paths never fall back to the admin (user_id=1) credential
//   - env LONGPORT_* keys are quote/collection fallback only, never used to
//     submit when a per-user DB row is missing
//   - halt Redis key sfp:trade:halt still blocks all new orders

const HaltRedisKey = "sfp:trade:halt"

// AllowSim is intentionally a no-op leftover detector. Callers must not pass
// allow_sim to the broker; this helper exists so tests can assert the flag is gone.
func DeprecatedPaperFlagsPresent() []string {
	var found []string
	for _, key := range []string{"LONGPORT_PAPERTRADING", "LONGPORT_TRADING_ENABLED", "REQUIRE_PAPER"} {
		if os.Getenv(key) != "" {
			found = append(found, key)
		}
	}
	return found
}

// SubmitGated reports whether this user/settings combination may hit the broker.
// execute is the job-level "try to place" flag; auto_trade_enabled is the account switch.
func SubmitGated(execute, configured, autoTradeEnabled, halted bool, haltReason string) (ok bool, reason string) {
	if halted {
		extra := haltReason
		if extra != "" {
			return false, "紧急停机中，禁止新委托：" + extra
		}
		return false, "紧急停机中，禁止新委托"
	}
	return ResolveSubmitPermission(execute, configured, autoTradeEnabled)
}
