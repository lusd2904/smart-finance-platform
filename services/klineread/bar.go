package klineread

// Bar is the shared OHLC shape used by market-read / trade-api (pointer fields)
// and converted to value bars in notify/quant workers.
type Bar struct {
	Date   string
	Open   *float64
	High   *float64
	Low    *float64
	Close  *float64
	Volume *float64
}

// ValueBar is the worker-side bar (non-pointer floats).
type ValueBar struct {
	Date   string
	Open   float64
	High   float64
	Low    float64
	Close  float64
	Volume float64
}

func ptr(v float64) *float64 { return &v }

func deref(v *float64) float64 {
	if v == nil {
		return 0
	}
	return *v
}

func barFromValues(date string, open, high, low, close, volume float64) Bar {
	return Bar{
		Date:   date,
		Open:   ptr(open),
		High:   ptr(high),
		Low:    ptr(low),
		Close:  ptr(close),
		Volume: ptr(volume),
	}
}

// ToValueBars maps pointer bars to worker value bars (nil OHLC → 0).
func ToValueBars(bars []Bar) []ValueBar {
	out := make([]ValueBar, 0, len(bars))
	for _, b := range bars {
		out = append(out, ValueBar{
			Date:   b.Date,
			Open:   deref(b.Open),
			High:   deref(b.High),
			Low:    deref(b.Low),
			Close:  deref(b.Close),
			Volume: deref(b.Volume),
		})
	}
	return out
}

func valueBarMap(in map[string][]Bar) map[string][]ValueBar {
	out := make(map[string][]ValueBar, len(in))
	for sym, bars := range in {
		out[sym] = ToValueBars(bars)
	}
	return out
}
