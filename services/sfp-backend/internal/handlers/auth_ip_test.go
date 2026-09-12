package handlers

import (
	"net/http"
	"testing"
)

func TestRequestClientIP(t *testing.T) {
	req, _ := http.NewRequest(http.MethodPost, "/login", nil)
	req.RemoteAddr = "192.0.2.10:54321"
	if got := requestClientIP(req); got != "192.0.2.10" {
		t.Fatalf("remote addr = %q", got)
	}

	req.Header.Set("X-Real-IP", "198.51.100.8")
	if got := requestClientIP(req); got != "198.51.100.8" {
		t.Fatalf("x-real-ip = %q", got)
	}

	req.Header.Set("X-Forwarded-For", "203.0.113.7, 10.0.0.1")
	if got := requestClientIP(req); got != "203.0.113.7" {
		t.Fatalf("xff = %q", got)
	}
}
