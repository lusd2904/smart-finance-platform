package store

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestFeaturedSymbolsPinsMarketIndices(t *testing.T) {
	hk := featuredSymbols("HK")
	for _, want := range []string{"0700.HK", "9988.HK", "3690.HK", "HSI", "HSTECH", "HSCEI"} {
		if !containsSymbol(hk, want) {
			t.Fatalf("HK featured missing %s: %v", want, hk)
		}
	}
	cn := featuredSymbols("CN")
	for _, want := range []string{"600519.SH", "000001.SZ", "000001.SH", "399001", "399006"} {
		if !containsSymbol(cn, want) {
			t.Fatalf("CN featured missing %s: %v", want, cn)
		}
	}
	if containsSymbol(cn, "000001") {
		t.Fatalf("bare 000001 must not be featured as 上证 (it is 平安银行): %v", cn)
	}
	if !containsSymbol(cn, "000001.SZ") {
		t.Fatal("000001.SZ (平安银行) must remain a featured stock")
	}
	if !containsSymbol(cn, "000001.SH") {
		t.Fatal("000001.SH (上证指数) must be pinned as a featured CN index")
	}
}

func TestSQLInsertsShanghaiCompositeAs000001SH(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("..", "..", "..", "..", "sql", "market-index-instruments.sql"))
	if err != nil {
		t.Fatal(err)
	}
	text := string(raw)
	if !strings.Contains(text, "'000001.SH'") {
		t.Fatal("SQL must INSERT 000001.SH as 上证指数")
	}
	if strings.Contains(text, "('000001'") {
		t.Fatal("SQL must not INSERT or UPDATE bare 000001 (live row is 平安银行)")
	}
}

func containsSymbol(list []string, want string) bool {
	for _, item := range list {
		if item == want {
			return true
		}
	}
	return false
}
