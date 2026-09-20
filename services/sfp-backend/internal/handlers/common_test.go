package handlers

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/config"
)

func TestResolveUnderRoot(t *testing.T) {
	root := t.TempDir()
	if _, ok := resolveUnderRoot(root, ""); ok {
		t.Fatal("empty")
	}
	if _, ok := resolveUnderRoot(root, ".."); ok {
		t.Fatal("..")
	}
	if _, ok := resolveUnderRoot(root, "../secret"); ok {
		t.Fatal("relative escape")
	}
	if _, ok := resolveUnderRoot(root, "/etc/passwd"); ok {
		t.Fatal("absolute")
	}
	got, ok := resolveUnderRoot(root, "a/b.txt")
	if !ok {
		t.Fatal("relative under root")
	}
	want := filepath.Join(root, "a", "b.txt")
	if got != want {
		t.Fatalf("got %s want %s", got, want)
	}
}

func TestCommonDownloadRejectsTraversal(t *testing.T) {
	root := t.TempDir()
	s := &Server{Config: &config.Config{DownloadPath: root, UploadPath: root}}
	req := httptest.NewRequest(http.MethodGet, "/common/download?fileName=../secret", nil)
	rec := httptest.NewRecorder()
	s.CommonDownload(rec, req)
	if !strings.Contains(rec.Body.String(), "文件名称不合法") {
		t.Fatalf("body=%s", rec.Body.String())
	}

	req = httptest.NewRequest(http.MethodGet, "/common/download/resource?resource=../secret", nil)
	rec = httptest.NewRecorder()
	s.CommonDownloadResource(rec, req)
	if !strings.Contains(rec.Body.String(), "资源路径不合法") {
		t.Fatalf("escape body=%s", rec.Body.String())
	}

	req = httptest.NewRequest(http.MethodGet, "/common/download/resource?resource=//etc/passwd", nil)
	rec = httptest.NewRecorder()
	s.CommonDownloadResource(rec, req)
	if !strings.Contains(rec.Body.String(), "资源路径不合法") {
		t.Fatalf("abs body=%s", rec.Body.String())
	}
}

func TestCommonDownloadServesInsideRoot(t *testing.T) {
	root := t.TempDir()
	path := filepath.Join(root, "ok.txt")
	if err := os.WriteFile(path, []byte("hi"), 0o644); err != nil {
		t.Fatal(err)
	}
	s := &Server{Config: &config.Config{DownloadPath: root}}
	req := httptest.NewRequest(http.MethodGet, "/common/download?fileName=ok.txt", nil)
	rec := httptest.NewRecorder()
	s.CommonDownload(rec, req)
	if rec.Code != http.StatusOK || rec.Body.String() != "hi" {
		t.Fatalf("code=%d body=%q", rec.Code, rec.Body.String())
	}
}
