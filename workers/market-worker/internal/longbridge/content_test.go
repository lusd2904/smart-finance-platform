package longbridge

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestToSymbol(t *testing.T) {
	cases := map[[2]string]string{
		{"AAPL", "US"}:    "AAPL.US",
		{"AAPL.US", "US"}: "AAPL.US",
		{"0700", "HK"}:    "0700.HK",
		{"600519", "CN"}:  "600519.SH",
		{"000001", "CN"}:  "000001.SZ",
		{"^GSPC", "US"}:   "^GSPC",
	}
	for in, want := range cases {
		if got := ToSymbol(in[0], in[1]); got != want {
			t.Fatalf("ToSymbol(%s,%s)=%s want %s", in[0], in[1], got, want)
		}
	}
}

func TestCredsBaseURL(t *testing.T) {
	if (Creds{Region: "cn"}).BaseURL() != "https://openapi.longbridge.cn" {
		t.Fatal("cn endpoint")
	}
	if (Creds{Region: "us"}).BaseURL() != "https://openapi.longbridge.com" {
		t.Fatal("intl endpoint")
	}
	if (Creds{HTTPURL: "https://example.test/"}).BaseURL() != "https://example.test" {
		t.Fatal("override")
	}
}

func TestFetchSymbolContentHTTP(t *testing.T) {
	var sawAuth bool
	var sawFilings, sawNews, sawTopics bool
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("x-api-key") != "k" || r.Header.Get("authorization") != "tok" || r.Header.Get("x-api-signature") == "" {
			http.Error(w, "unsigned", http.StatusUnauthorized)
			return
		}
		sawAuth = true
		switch {
		case strings.Contains(r.URL.Path, "/filings"):
			sawFilings = true
			if r.URL.Query().Get("symbol") != "AAPL.US" {
				http.Error(w, "symbol", 400)
				return
			}
			io.WriteString(w, `{"code":0,"data":{"items":[{"id":"f1","title":"10-K","description":"filing","file_urls":["https://sec.example/a"],"publish_at":"1770000000"}]}}`)
		case strings.HasSuffix(r.URL.Path, "/news"):
			sawNews = true
			io.WriteString(w, `{"code":0,"data":{"items":[{"id":"n1","title":"Apple news","description":"body","url":"https://lb.example/n1","published_at":"1770000001"}]}}`)
		case strings.HasSuffix(r.URL.Path, "/topics"):
			sawTopics = true
			io.WriteString(w, `{"code":0,"data":{"items":[{"id":"t1","title":"Topic","description":"talk","url":"https://lb.example/t1","published_at":"1770000002"}]}}`)
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	cli := NewClient(Creds{AppKey: "k", AppSecret: "s", AccessToken: "tok", HTTPURL: srv.URL})
	cli.Now = func() time.Time { return time.UnixMilli(1770000000000) }
	bundle, err := cli.FetchSymbolContent(context.Background(), "AAPL.US", []string{"announcement", "news", "topic"})
	if err != nil {
		t.Fatal(err)
	}
	if !sawAuth || !sawFilings || !sawNews || !sawTopics {
		t.Fatalf("paths auth=%v f=%v n=%v t=%v", sawAuth, sawFilings, sawNews, sawTopics)
	}
	if len(bundle["announcement"]) != 1 || bundle["announcement"][0].URL != "https://sec.example/a" {
		t.Fatalf("filings=%+v", bundle["announcement"])
	}
	if len(bundle["news"]) != 1 || bundle["news"][0].Title != "Apple news" {
		t.Fatalf("news=%+v", bundle["news"])
	}
	if bundle["announcement"][0].PublishedAt == nil {
		t.Fatal("publish_at")
	}
}

func TestFetchSymbolContentUnconfigured(t *testing.T) {
	cli := NewClient(Creds{})
	bundle, err := cli.FetchSymbolContent(context.Background(), "AAPL.US", []string{"news"})
	if err != nil {
		t.Fatal(err)
	}
	if len(bundle["news"]) != 0 {
		t.Fatalf("%+v", bundle)
	}
}

func TestFetchSymbolContentAPIError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		io.WriteString(w, `{"code":401004,"message":"access token invalid"}`)
	}))
	defer srv.Close()
	cli := NewClient(Creds{AppKey: "k", AppSecret: "s", AccessToken: "tok", HTTPURL: srv.URL})
	_, err := cli.FetchSymbolContent(context.Background(), "AAPL.US", []string{"news"})
	if err == nil || !strings.Contains(err.Error(), "401004") {
		t.Fatalf("err=%v", err)
	}
}
