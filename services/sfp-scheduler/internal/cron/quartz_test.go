package cron

import (
	"testing"
	"time"
)

func shanghai(t *testing.T) *time.Location {
	t.Helper()
	loc, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		t.Fatal(err)
	}
	return loc
}

func mustParse(t *testing.T, expr string, loc *time.Location) *Schedule {
	t.Helper()
	s, err := Parse(expr, loc)
	if err != nil {
		t.Fatalf("parse %q: %v", expr, err)
	}
	return s
}

func TestParseRejectsWrongFieldCount(t *testing.T) {
	_, err := Parse("0 15 * * *", shanghai(t))
	if err == nil {
		t.Fatal("expected error for 5-field cron")
	}
}

func TestParseRejectsLW(t *testing.T) {
	if _, err := Parse("0 0 0 L * ?", shanghai(t)); err == nil {
		t.Fatal("expected error for L")
	}
}

func TestNextEveryNMinutesShanghai(t *testing.T) {
	loc := shanghai(t)
	s := mustParse(t, "0 0/15 * * * ?", loc)
	from := time.Date(2026, 9, 8, 10, 7, 30, 0, loc)
	got := s.Next(from)
	want := time.Date(2026, 9, 8, 10, 15, 0, 0, loc)
	if !got.Equal(want) {
		t.Fatalf("next=%s want=%s", got, want)
	}
}

func TestNextHourlyAtMinuteShanghai(t *testing.T) {
	loc := shanghai(t)
	s := mustParse(t, "0 15 * * * ?", loc)
	from := time.Date(2026, 9, 8, 10, 15, 0, 0, loc)
	got := s.Next(from)
	want := time.Date(2026, 9, 8, 11, 15, 0, 0, loc)
	if !got.Equal(want) {
		t.Fatalf("next=%s want=%s", got, want)
	}
}

func TestNextDailyClockShanghai(t *testing.T) {
	loc := shanghai(t)
	s := mustParse(t, "0 30 5 * * ?", loc)
	from := time.Date(2026, 9, 8, 4, 0, 0, 0, loc)
	got := s.Next(from)
	want := time.Date(2026, 9, 8, 5, 30, 0, 0, loc)
	if !got.Equal(want) {
		t.Fatalf("next=%s want=%s", got, want)
	}
	from = time.Date(2026, 9, 8, 5, 30, 0, 0, loc)
	got = s.Next(from)
	want = time.Date(2026, 9, 9, 5, 30, 0, 0, loc)
	if !got.Equal(want) {
		t.Fatalf("next after fire=%s want=%s", got, want)
	}
}

func TestNextHourList(t *testing.T) {
	loc := shanghai(t)
	s := mustParse(t, "0 50 7,8,21 * * ?", loc)
	from := time.Date(2026, 9, 8, 8, 51, 0, 0, loc)
	got := s.Next(from)
	want := time.Date(2026, 9, 8, 21, 50, 0, 0, loc)
	if !got.Equal(want) {
		t.Fatalf("next=%s want=%s", got, want)
	}
}

func TestAnalysisJobCronsParse(t *testing.T) {
	loc := shanghai(t)
	exprs := []string{
		"0 30 5 * * ?",
		"0 15 * * * ?",
		"0 0/30 * * * ?",
		"0 0/15 * * * ?",
		"0 5 7 * * ?",
		"0 5 8 * * ?",
		"0 5 21 * * ?",
		"0 0/5 * * * ?",
		"0 25 7 * * ?",
		"0 25 8 * * ?",
		"0 25 21 * * ?",
		"0 50 7,8,21 * * ?",
		"0 0/10 * * * ?",
	}
	from := time.Date(2026, 9, 8, 12, 0, 0, 0, loc)
	for _, expr := range exprs {
		s := mustParse(t, expr, loc)
		next := s.Next(from)
		if next.IsZero() {
			t.Fatalf("%q produced no next fire", expr)
		}
		if next.Location().String() != "Asia/Shanghai" {
			t.Fatalf("%q next location=%s", expr, next.Location())
		}
	}
}

func TestUTCVsShanghaiSameExpression(t *testing.T) {
	expr := "0 25 7 * * ?"
	sh := mustParse(t, expr, shanghai(t))
	utc := mustParse(t, expr, time.UTC)
	fromSH := time.Date(2026, 9, 8, 0, 0, 0, 0, shanghai(t))
	fromUTC := time.Date(2026, 9, 8, 0, 0, 0, 0, time.UTC)
	gotSH := sh.Next(fromSH)
	gotUTC := utc.Next(fromUTC)
	if gotSH.Hour() != 7 || gotSH.Minute() != 25 {
		t.Fatalf("shanghai wall clock = %s", gotSH)
	}
	if gotUTC.Hour() != 7 || gotUTC.Minute() != 25 {
		t.Fatalf("utc wall clock = %s", gotUTC)
	}
	if gotSH.Equal(gotUTC) {
		t.Fatal("Asia/Shanghai and UTC next times should differ for the same wall-clock cron")
	}
}

func TestPrevOrEqual(t *testing.T) {
	loc := shanghai(t)
	s := mustParse(t, "0 0/5 * * * ?", loc)
	from := time.Date(2026, 9, 8, 10, 7, 0, 0, loc)
	prev := s.PrevOrEqual(from, time.Hour)
	want := time.Date(2026, 9, 8, 10, 5, 0, 0, loc)
	if !prev.Equal(want) {
		t.Fatalf("prev=%s want=%s", prev, want)
	}
}
