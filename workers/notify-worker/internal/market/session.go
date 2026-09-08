package market

import (
	"time"
)

var marketTZ = map[string]string{
	"CN": "Asia/Shanghai",
	"HK": "Asia/Hong_Kong",
	"US": "America/New_York",
}

type sessionWindow struct {
	startHour, startMin int
	endHour, endMin     int
}

var sessions = map[string][]sessionWindow{
	"CN": {{9, 30, 11, 30}, {13, 0, 15, 0}},
	"HK": {{9, 30, 12, 0}, {13, 0, 16, 0}},
	"US": {{9, 30, 16, 0}},
}

// IsInSession mirrors Python index_session.is_in_session (weekday + local hours).
func IsInSession(market string, now time.Time) bool {
	market = normalizeMarket(market)
	locName := marketTZ[market]
	if locName == "" {
		return false
	}
	loc, err := time.LoadLocation(locName)
	if err != nil {
		return false
	}
	local := now.In(loc)
	if local.Weekday() == time.Saturday || local.Weekday() == time.Sunday {
		return false
	}
	h, m, _ := local.Clock()
	cur := h*60 + m
	for _, w := range sessions[market] {
		start := w.startHour*60 + w.startMin
		end := w.endHour*60 + w.endMin
		if cur >= start && cur < end {
			return true
		}
	}
	return false
}

func ListSessionStatus(now time.Time) map[string]map[string]interface{} {
	out := map[string]map[string]interface{}{}
	for market, tzName := range marketTZ {
		loc, _ := time.LoadLocation(tzName)
		local := now.In(loc)
		out[market] = map[string]interface{}{
			"market":    market,
			"open":      IsInSession(market, now),
			"localTime": local.Format("2006-01-02 15:04:05"),
			"timezone":  tzName,
		}
	}
	return out
}

func normalizeMarket(market string) string {
	switch market {
	case "US", "HK", "CN":
		return market
	default:
		return "US"
	}
}
