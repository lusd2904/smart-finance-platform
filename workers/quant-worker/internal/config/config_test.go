package config

import "testing"

func TestDefaultDatabaseIsSentimentAI(t *testing.T) {
	t.Setenv("DB_DATABASE", "")
	cfg := Load()
	if cfg.MySQLDatabase != "sentiment-ai" {
		t.Fatalf("got %q", cfg.MySQLDatabase)
	}
}
