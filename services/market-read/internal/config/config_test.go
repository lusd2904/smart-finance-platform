package config

import "testing"

func TestLoadDoesNotRequireInfluxToken(t *testing.T) {
	t.Setenv("JWT_SECRET_KEY", "secret")
	t.Setenv("DB_PASSWORD", "pass")
	t.Setenv("INFLUX_TOKEN", "")
	cfg, err := Load()
	if err != nil {
		t.Fatalf("reads are MySQL-only; INFLUX_TOKEN must not be required: %v", err)
	}
	if cfg.JWTSecret != "secret" || cfg.MySQLPassword != "pass" {
		t.Fatalf("jwt/db not loaded: %+v", cfg)
	}
	if cfg.InfluxToken != "" {
		t.Fatalf("empty INFLUX_TOKEN should stay empty, got %q", cfg.InfluxToken)
	}
}

func TestLoadRequiresJWTAndDBPassword(t *testing.T) {
	t.Setenv("JWT_SECRET_KEY", "")
	t.Setenv("DB_PASSWORD", "pass")
	if _, err := Load(); err == nil {
		t.Fatal("JWT_SECRET_KEY must be required")
	}
	t.Setenv("JWT_SECRET_KEY", "secret")
	t.Setenv("DB_PASSWORD", "")
	if _, err := Load(); err == nil {
		t.Fatal("DB_PASSWORD must be required")
	}
}
