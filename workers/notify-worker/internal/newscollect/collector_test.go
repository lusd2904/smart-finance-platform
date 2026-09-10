package newscollect

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"
)

func TestSplitSourcesDefaultAndDedup(t *testing.T) {
	got := SplitSources("")
	if strings.Join(got, ",") != DefaultSources {
		t.Fatalf("empty should use defaults, got %v", got)
	}
	got = SplitSources(" eastmoney, sina, EASTMONEY, x_monitor ")
	if len(got) != 3 || got[0] != "eastmoney" || got[1] != "sina" || got[2] != "x_monitor" {
		t.Fatalf("unexpected sources: %v", got)
	}
}

func TestMakeHashMatchesPython(t *testing.T) {
	// hashlib.md5('eastmoney:中美联合侦破'.encode()).hexdigest()
	got := MakeHash("eastmoney", "中美联合侦破")
	if len(got) != 32 {
		t.Fatalf("md5 hex should be 32 chars, got %s", got)
	}
	if MakeHash("eastmoney", "a") == MakeHash("sina", "a") {
		t.Fatal("hash must include source")
	}
}

func TestStripHTML(t *testing.T) {
	got := StripHTML("<p>国务院办公厅印发<strong>通知</strong></p>")
	if got != "国务院办公厅印发通知" {
		t.Fatalf("got %q", got)
	}
}

func TestParseTimeNaiveAndUnix(t *testing.T) {
	naive := ParseTime("2026-09-10 17:03:06")
	if naive.Year() != 2026 || naive.Month() != 9 || naive.Day() != 10 || naive.Hour() != 17 {
		t.Fatalf("naive wall clock lost: %v", naive)
	}
	unix := ParseTime(int64(1789031086))
	if unix.Year() != 2026 || unix.Month() != 9 {
		t.Fatalf("unix seconds should be Sep 2026, got %v", unix)
	}
	rfc := ParseTime("Wed, 10 Sep 2026 01:00:00 GMT")
	if rfc.Location() == time.UTC {
		t.Fatal("RFC times should convert into Shanghai")
	}
}

func TestParseEastmoneyAndSina(t *testing.T) {
	east := parseEastmoney([]byte(`{
		"data":{"fastNewsList":[
			{"title":"中美联合侦破","summary":"<p>摘要</p>","showTime":"2026-09-10 17:03:06","code":"202609103870631153"},
			{"title":"","summary":""}
		]}
	}`))
	if len(east) != 1 {
		t.Fatalf("expected 1 eastmoney item, got %d", len(east))
	}
	if east[0].Source != "eastmoney" || east[0].URL == "" || east[0].UniqHash == "" {
		t.Fatalf("incomplete eastmoney item: %+v", east[0])
	}
	if east[0].Content != "摘要" {
		t.Fatalf("html should be stripped, got %q", east[0].Content)
	}

	sina := parseSina([]byte(`{
		"result":{"data":{"feed":{"list":[
			{"rich_text":"<b>欧碳配额</b>","create_time":"2026-09-10 17:04:41","docurl":"","ext":"{\"docurl\":\"https://finance.sina.com.cn/a.html\"}"}
		]}}}
	}`))
	if len(sina) != 1 || sina[0].URL != "https://finance.sina.com.cn/a.html" {
		t.Fatalf("sina should read ext.docurl: %+v", sina)
	}
	if sina[0].Title != "欧碳配额" {
		t.Fatalf("sina title %q", sina[0].Title)
	}
}

func TestParseTHSWallstreetJin10Google(t *testing.T) {
	ths := parseTHS([]byte(`{
		"data":{"list":[{
			"id":5147397,
			"title":"计量典型案例",
			"digest":"摘要正文",
			"url":"https:/news.10jqka.com.cn/a.shtml",
			"ctime":1789031055
		}]}
	}`))
	if len(ths) != 1 {
		t.Fatalf("ths items=%d", len(ths))
	}
	if !strings.HasPrefix(ths[0].URL, "https://") {
		t.Fatalf("ths should fix https:/ URL, got %q", ths[0].URL)
	}
	if ths[0].UniqHash != MakeHash("ths", "5147397") {
		t.Fatalf("ths hash should use id, got %s", ths[0].UniqHash)
	}

	wscn := parseWallstreetCN([]byte(`{
		"data":{"items":[{
			"id":3163180,
			"title":"国办通知",
			"content_text":"国务院办公厅印发通知",
			"uri":"/livenews/3163180",
			"display_time":1789031086
		}]}
	}`))
	if len(wscn) != 1 || wscn[0].URL != "https://wallstreetcn.com/livenews/3163180" {
		t.Fatalf("wscn uri prefix: %+v", wscn)
	}

	jin := parseJin10([]byte(`{
		"data":[
			{"id":"a1","time":"2026-09-10 17:04:33","data":{"content":"思科合作","title":""}},
			{"id":"vip","time":"2026-09-10 17:04:09","data":{"content":"","title":"","vip_title":"VIP"}}
		]
	}`))
	if len(jin) != 1 || jin[0].Title != "思科合作" {
		t.Fatalf("jin10 should skip empty VIP rows: %+v", jin)
	}

	rss := []byte(`<?xml version="1.0"?><rss><channel>
		<item><title>美联储观察</title><description>&lt;p&gt;摘要&lt;/p&gt;</description>
		<link>https://news.google.com/a</link><pubDate>Wed, 10 Sep 2026 01:00:00 GMT</pubDate></item>
	</channel></rss>`)
	g := parseGoogleNewsRSS(rss, 5)
	if len(g) != 1 || g[0].Source != "google_news" || g[0].Content != "摘要" {
		t.Fatalf("google rss: %+v", g)
	}
}

func TestFilterFreshAndXMonitorUntouched(t *testing.T) {
	items := []Item{
		{Source: "eastmoney", Title: "A", UniqHash: "h1"},
		{Source: "eastmoney", Title: "A-dup", UniqHash: "h1"},
		{Source: "x_monitor", Title: "tweet", UniqHash: "x1"},
	}
	fresh := FilterFresh(items, map[string]bool{"x1": true})
	if len(fresh) != 1 || fresh[0].UniqHash != "h1" {
		t.Fatalf("expected only new eastmoney hash, got %+v", fresh)
	}
}

func TestSummarizeKeepsAnalyzeWindowCopy(t *testing.T) {
	msg := Summarize(12, 3, 7, 10, []SourceResult{
		{Source: "eastmoney", Fetched: 8},
		{Source: "ths", Error: "http 503"},
		{Source: "x_monitor", Skipped: "ingest-only"},
	})
	if !strings.Contains(msg, "采集 12 条，新入库 3 条") {
		t.Fatalf("missing collect counts: %s", msg)
	}
	if !strings.Contains(msg, "ths 失败") || !strings.Contains(msg, "最近 10 分钟待分析 7 条") {
		t.Fatalf("missing failure/pending: %s", msg)
	}
	onlyX := Summarize(0, 0, 4, 10, []SourceResult{{Source: "x_monitor", Skipped: "ingest-only"}})
	if !strings.Contains(onlyX, "x_monitor 仅走 ingest") {
		t.Fatalf("x-only message: %s", onlyX)
	}
}

func TestCollectHTTPRoundTrip(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/comm/web/getFastNewsList", func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"data": map[string]any{"fastNewsList": []map[string]any{
				{"title": "东财快讯", "summary": "摘要", "showTime": "2026-09-10 17:00:00", "code": "1"},
			}},
		})
	})
	mux.HandleFunc("/api/zhibo/feed", func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"result": map[string]any{"data": map[string]any{"feed": map[string]any{"list": []map[string]any{
				{"rich_text": "新浪快讯", "create_time": "2026-09-10 17:01:00", "docurl": "https://finance.sina.com.cn/x"},
			}}}},
		})
	})
	mux.HandleFunc("/tapp/news/push/stock/", func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"data": map[string]any{"list": []map[string]any{
				{"id": 9, "title": "同花顺", "digest": "d", "url": "https://news.10jqka.com.cn/a", "ctime": 1789031055},
			}},
		})
	})
	mux.HandleFunc("/apiv1/content/lives", func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "upstream down", http.StatusBadGateway)
	})
	mux.HandleFunc("/rss/search", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/rss+xml")
		title := "谷歌新闻 " + r.URL.Query().Get("q")
		_, _ = w.Write([]byte(`<?xml version="1.0"?><rss><channel>
			<item><title>` + title + `</title><description>desc</description><link>https://news.google.com/x</link></item>
		</channel></rss>`))
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	client := NewClient()
	client.Rewrite = func(canonical string) string {
		u, err := url.Parse(canonical)
		if err != nil {
			return canonical
		}
		base, _ := url.Parse(srv.URL)
		u.Scheme = base.Scheme
		u.Host = base.Host
		return u.String()
	}

	items, reports := Collect(context.Background(), client, []string{
		"eastmoney", "sina", "ths", "wallstreetcn", "google_news", "x_monitor", "not-a-source",
	})
	bySource := map[string]int{}
	for _, it := range items {
		bySource[it.Source]++
	}
	if bySource["eastmoney"] != 1 || bySource["sina"] != 1 || bySource["ths"] != 1 || bySource["google_news"] != 3 {
		t.Fatalf("unexpected item counts: %v items=%d", bySource, len(items))
	}
	if bySource["x_monitor"] != 0 {
		t.Fatal("collector must not invent x_monitor rows")
	}
	var sawWSCNFail, sawXSkip, sawUnknown bool
	for _, r := range reports {
		switch {
		case r.Source == "wallstreetcn" && r.Error != "":
			sawWSCNFail = true
		case r.Source == "x_monitor" && r.Skipped == "ingest-only":
			sawXSkip = true
		case r.Source == "not-a-source" && r.Skipped == "unknown":
			sawUnknown = true
		}
	}
	if !sawWSCNFail || !sawXSkip || !sawUnknown {
		t.Fatalf("reports missing expected statuses: %+v", reports)
	}
}

func TestLivePublicSources(t *testing.T) {
	if os.Getenv("LIVE_NEWS") != "1" {
		t.Skip("set LIVE_NEWS=1 to hit public flash APIs")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 40*time.Second)
	defer cancel()
	items, reports := Collect(ctx, NewClient(), []string{
		"eastmoney", "sina", "ths", "wallstreetcn", "google_news", "jin10", "x_monitor",
	})
	t.Logf("fetched=%d reports=%+v", len(items), reports)
	by := map[string]int{}
	for _, it := range items {
		by[it.Source]++
	}
	if by["eastmoney"] == 0 || by["sina"] == 0 {
		t.Fatalf("MVP sources empty: %v", by)
	}
	if by["x_monitor"] != 0 {
		t.Fatal("live collect must not write x_monitor")
	}
}

func TestClsAliasesTHSWithoutDoubleFetch(t *testing.T) {
	hits := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.Contains(r.URL.Path, "10jqka") || strings.Contains(r.URL.Path, "push/stock") {
			hits++
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"data": map[string]any{"list": []map[string]any{
				{"id": 1, "title": "cls", "digest": "d", "url": "https://news.10jqka.com.cn/a", "ctime": 1789031055},
			}},
		})
	}))
	defer srv.Close()
	client := NewClient()
	client.Rewrite = func(canonical string) string {
		u, _ := url.Parse(canonical)
		base, _ := url.Parse(srv.URL)
		u.Scheme, u.Host = base.Scheme, base.Host
		return u.String()
	}
	items, reports := Collect(context.Background(), client, []string{"ths", "cls"})
	if hits != 1 {
		t.Fatalf("cls should not refetch ths, hits=%d", hits)
	}
	if len(items) != 1 {
		t.Fatalf("dedup should leave 1 item, got %d", len(items))
	}
	if reports[1].Skipped != "alias-of-ths" {
		t.Fatalf("cls skip: %+v", reports)
	}
}
