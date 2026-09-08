// Package cron parses RuoYi / Quartz 6–7 field expressions and computes
// next fire times in a named timezone (default Asia/Shanghai).
//
// Field order: second minute hour day-of-month month day-of-week [year]
//
// Supported syntax (covers every analysis sys_job row):
//   - "*" / "?" (unspecified; "?" is treated as unset for day/dow)
//   - lists "7,8,21", ranges "1-5", steps "0/15" / "*/10"
//
// Quartz-only tokens L / W / # are rejected so we do not silently
// mis-schedule. Python MyCronTrigger has partial L/W/# support; none of
// the analysis jobs use those tokens.
package cron

import (
	"fmt"
	"strconv"
	"strings"
	"time"
)

const (
	minFields = 6
	maxFields = 7
)

type field struct {
	any    bool
	values map[int]struct{}
}

func (f field) match(v int) bool {
	if f.any {
		return true
	}
	_, ok := f.values[v]
	return ok
}

// Schedule is a parsed Quartz cron in a fixed location.
type Schedule struct {
	Raw      string
	Location *time.Location
	sec      field
	min      field
	hour     field
	dom      field
	month    field
	dow      field
	year     field
	domSet   bool
	dowSet   bool
}

func Parse(expr string, loc *time.Location) (*Schedule, error) {
	expr = strings.TrimSpace(expr)
	if expr == "" {
		return nil, fmt.Errorf("empty cron expression")
	}
	if loc == nil {
		loc = time.UTC
	}
	parts := strings.Fields(expr)
	if len(parts) != minFields && len(parts) != maxFields {
		return nil, fmt.Errorf("wrong number of cron fields: got %d, want 6 or 7", len(parts))
	}
	for _, p := range parts {
		if strings.ContainsAny(p, "LW#") {
			return nil, fmt.Errorf("unsupported Quartz token in %q (L/W/# not implemented)", expr)
		}
	}
	sec, err := parseField(parts[0], 0, 59)
	if err != nil {
		return nil, fmt.Errorf("second: %w", err)
	}
	min, err := parseField(parts[1], 0, 59)
	if err != nil {
		return nil, fmt.Errorf("minute: %w", err)
	}
	hour, err := parseField(parts[2], 0, 23)
	if err != nil {
		return nil, fmt.Errorf("hour: %w", err)
	}
	dom, domSet, err := parseDayField(parts[3], 1, 31)
	if err != nil {
		return nil, fmt.Errorf("day-of-month: %w", err)
	}
	month, err := parseField(parts[4], 1, 12)
	if err != nil {
		return nil, fmt.Errorf("month: %w", err)
	}
	dow, dowSet, err := parseDayField(parts[5], 0, 7)
	if err != nil {
		return nil, fmt.Errorf("day-of-week: %w", err)
	}
	year := field{any: true}
	if len(parts) == maxFields {
		year, err = parseField(parts[6], 1970, 2099)
		if err != nil {
			return nil, fmt.Errorf("year: %w", err)
		}
	}
	return &Schedule{
		Raw:      expr,
		Location: loc,
		sec:      sec,
		min:      min,
		hour:     hour,
		dom:      dom,
		month:    month,
		dow:      dow,
		year:     year,
		domSet:   domSet,
		dowSet:   dowSet,
	}, nil
}

func parseDayField(raw string, minV, maxV int) (field, bool, error) {
	if raw == "?" {
		return field{any: true}, false, nil
	}
	f, err := parseField(raw, minV, maxV)
	if err != nil {
		return field{}, false, err
	}
	return f, !f.any, nil
}

func parseField(raw string, minV, maxV int) (field, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return field{}, fmt.Errorf("empty field")
	}
	if raw == "*" || raw == "?" {
		return field{any: true}, nil
	}
	out := field{values: map[int]struct{}{}}
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		if part == "" {
			return field{}, fmt.Errorf("empty list item")
		}
		if err := addPart(out.values, part, minV, maxV); err != nil {
			return field{}, err
		}
	}
	if len(out.values) == 0 {
		return field{}, fmt.Errorf("field %q matched no values", raw)
	}
	return out, nil
}

func addPart(dst map[int]struct{}, part string, minV, maxV int) error {
	step := 1
	rangePart := part
	if i := strings.IndexByte(part, '/'); i >= 0 {
		rangePart = part[:i]
		n, err := strconv.Atoi(part[i+1:])
		if err != nil || n <= 0 {
			return fmt.Errorf("invalid step in %q", part)
		}
		step = n
	}
	start, end := minV, maxV
	switch {
	case rangePart == "*" || rangePart == "?":
		// full range with step
	case rangePart == "":
		return fmt.Errorf("invalid field %q", part)
	default:
		if j := strings.IndexByte(rangePart, '-'); j >= 0 {
			a, err1 := strconv.Atoi(rangePart[:j])
			b, err2 := strconv.Atoi(rangePart[j+1:])
			if err1 != nil || err2 != nil {
				return fmt.Errorf("invalid range %q", rangePart)
			}
			start, end = a, b
		} else {
			n, err := strconv.Atoi(rangePart)
			if err != nil {
				return fmt.Errorf("invalid value %q", rangePart)
			}
			if strings.Contains(part, "/") {
				start, end = n, maxV
			} else {
				start, end = n, n
			}
		}
	}
	if start < minV || end > maxV || start > end {
		return fmt.Errorf("value out of range %d-%d in %q", minV, maxV, part)
	}
	for v := start; v <= end; v += step {
		dst[v] = struct{}{}
	}
	return nil
}

// Next returns the next fire time strictly after from, in the schedule location.
func (s *Schedule) Next(from time.Time) time.Time {
	t := from.In(s.Location).Add(time.Second).Truncate(time.Second)
	limit := t.AddDate(5, 0, 0)
	for t.Before(limit) {
		if !s.year.match(t.Year()) {
			t = time.Date(t.Year()+1, 1, 1, 0, 0, 0, 0, s.Location)
			continue
		}
		if !s.month.match(int(t.Month())) {
			t = time.Date(t.Year(), t.Month()+1, 1, 0, 0, 0, 0, s.Location)
			continue
		}
		if !s.matchDay(t) {
			t = time.Date(t.Year(), t.Month(), t.Day()+1, 0, 0, 0, 0, s.Location)
			continue
		}
		if !s.hour.match(t.Hour()) {
			t = time.Date(t.Year(), t.Month(), t.Day(), t.Hour()+1, 0, 0, 0, s.Location)
			continue
		}
		if !s.min.match(t.Minute()) {
			t = time.Date(t.Year(), t.Month(), t.Day(), t.Hour(), t.Minute()+1, 0, 0, s.Location)
			continue
		}
		if !s.sec.match(t.Second()) {
			t = t.Add(time.Second)
			continue
		}
		return t
	}
	return time.Time{}
}

func (s *Schedule) matchDay(t time.Time) bool {
	domOK := s.dom.match(t.Day())
	dowOK := s.matchDow(t.Weekday())
	switch {
	case s.domSet && s.dowSet:
		// Quartz: if both day-of-month and day-of-week are specified, OR them.
		return domOK || dowOK
	case s.domSet:
		return domOK
	case s.dowSet:
		return dowOK
	default:
		return true
	}
}

// Quartz Sunday=1 … Saturday=7; we also accept 0 as Sunday.
func (s *Schedule) matchDow(wd time.Weekday) bool {
	if s.dow.any {
		return true
	}
	quartz := int(wd) + 1 // Sunday=1
	if s.dow.match(quartz) {
		return true
	}
	if wd == time.Sunday && s.dow.match(0) {
		return true
	}
	return false
}

// PrevOrEqual returns the latest fire time at or before from, searching back
// at most lookback. Used for misfire catch-up.
func (s *Schedule) PrevOrEqual(from time.Time, lookback time.Duration) time.Time {
	from = from.In(s.Location)
	start := from.Add(-lookback)
	var prev time.Time
	cursor := start
	for {
		n := s.Next(cursor)
		if n.IsZero() || n.After(from) {
			return prev
		}
		prev = n
		cursor = n
	}
}
