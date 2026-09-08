package store

import (
	"database/sql"
	"testing"
)

func TestSerializeTop50IncludesExtras(t *testing.T) {
	rows := []Top50Row{
		{
			RankNo:        1,
			Symbol:        "600519",
			Name:          sql.NullString{String: "茅台", Valid: true},
			MarketCap:     sql.NullFloat64{Float64: 1.5e10, Valid: true},
			Turnover:      sql.NullFloat64{Float64: 8e9, Valid: true},
			ChangePct:     sql.NullFloat64{Float64: 1.1, Valid: true},
			Last:          sql.NullFloat64{Float64: 1500, Valid: true},
			ChangeAmount:  sql.NullFloat64{Float64: 16.5, Valid: true},
			TurnoverRate:  sql.NullFloat64{Float64: 0.85, Valid: true},
			VolumeRatio:   sql.NullFloat64{Float64: 1.6, Valid: true},
			Amplitude:     sql.NullFloat64{Float64: 2.4, Valid: true},
			PE:            sql.NullFloat64{Float64: 22.1, Valid: true},
			MainNetInflow: sql.NullFloat64{Float64: 1.2e8, Valid: true},
			Currency:      sql.NullString{String: "CNY", Valid: true},
		},
		{RankNo: 2, Symbol: "AAPL"},
	}
	out := SerializeTop50(rows)
	if len(out) != 2 {
		t.Fatalf("len=%d", len(out))
	}
	first := out[0]
	for _, key := range []string{"changeAmount", "turnoverRate", "volumeRatio", "amplitude", "pe", "mainNetInflow"} {
		if first[key] == nil {
			t.Fatalf("missing %s", key)
		}
	}
	if first["changeAmount"].(float64) != 16.5 || first["pe"].(float64) != 22.1 {
		t.Fatalf("values=%v", first)
	}
	second := out[1]
	if second["changeAmount"] != nil || second["mainNetInflow"] != nil || second["pe"] != nil {
		t.Fatalf("null extras should stay nil: %v", second)
	}
}
