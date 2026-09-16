package config

import "testing"

func TestInfluxDualWriteEnabled(t *testing.T) {
	cases := []struct {
		raw  string
		want bool
	}{
		{"", false},
		{"0", false},
		{"false", false},
		{"1", true},
		{"true", true},
		{"YES", true},
		{"on", true},
	}
	for _, tc := range cases {
		got := Config{InfluxDualWrite: tc.raw}.InfluxDualWriteEnabled()
		if got != tc.want {
			t.Fatalf("%q: got %v want %v", tc.raw, got, tc.want)
		}
	}
}
