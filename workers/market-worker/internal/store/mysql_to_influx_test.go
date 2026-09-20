package store

import (
	"context"
	"strings"
	"testing"
)

func TestMySQLToInfluxRequiresSymbol(t *testing.T) {
	s := &Service{}
	_, err := s.MySQLToInflux(context.Background(), "", "US")
	if err == nil {
		t.Fatal("empty symbol must be refused")
	}
	if !strings.Contains(err.Error(), "non-empty symbol") {
		t.Fatalf("err=%v", err)
	}
	_, err = s.MySQLToInflux(context.Background(), "   ", "CN")
	if err == nil {
		t.Fatal("whitespace symbol must be refused")
	}
}

func TestMySQLToInfluxNilWriterWithSymbol(t *testing.T) {
	s := &Service{}
	out, err := s.MySQLToInflux(context.Background(), "AAPL", "US")
	if err != nil {
		t.Fatalf("disabled influx should not error: %v", err)
	}
	if out["total_points"] != 0 {
		t.Fatalf("out=%v", out)
	}
}
