package handlers

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/guides"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/response"
)

var allowedUploadExt = map[string]bool{
	".bmp": true, ".gif": true, ".jpg": true, ".jpeg": true, ".png": true,
	".doc": true, ".docx": true, ".xls": true, ".xlsx": true, ".ppt": true, ".pptx": true,
	".html": true, ".htm": true, ".txt": true, ".rar": true, ".zip": true, ".gz": true, ".bz2": true,
	".mp4": true, ".avi": true, ".rmvb": true, ".pdf": true,
}

func (s *Server) CommonUpload(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseMultipartForm(32 << 20); err != nil {
		response.Error(w, "上传失败")
		return
	}
	file, header, err := r.FormFile("file")
	if err != nil {
		response.Error(w, "未找到上传文件")
		return
	}
	defer file.Close()
	ext := strings.ToLower(filepath.Ext(header.Filename))
	if !allowedUploadExt[ext] {
		response.Warn(w, "文件类型不合法")
		return
	}
	now := time.Now()
	relative := fmt.Sprintf("upload/%s/%s/%s", now.Format("2006"), now.Format("01"), now.Format("02"))
	dir := filepath.Join(s.Config.UploadPath, relative)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		response.Error(w, "创建上传目录失败")
		return
	}
	base := strings.TrimSuffix(header.Filename, ext)
	filename := fmt.Sprintf("%s_%s%04d%s", base, now.Format("20060102150405"), now.Nanosecond()%10000, ext)
	target := filepath.Join(dir, filename)
	out, err := os.Create(target)
	if err != nil {
		response.Error(w, "保存文件失败")
		return
	}
	if _, err := io.Copy(out, file); err != nil {
		out.Close()
		response.Error(w, "保存文件失败")
		return
	}
	out.Close()
	webPath := fmt.Sprintf("%s/%s/%s", s.Config.UploadPrefix, relative, filename)
	response.SuccessModel(w, "上传成功", map[string]interface{}{
		"fileName": webPath, "newFileName": filename, "originalFilename": header.Filename,
		"url": joinURL(r, strings.TrimPrefix(webPath, "/")),
	})
}

func (s *Server) CommonGuide(w http.ResponseWriter, r *http.Request) {
	module := strings.TrimPrefix(r.URL.Path, "/common/guide/")
	module = strings.Trim(module, "/")
	guide, err := guides.Load(module)
	if err != nil {
		response.Warn(w, "说明不存在")
		return
	}
	response.Success(w, guide)
}

func (s *Server) CommonDownload(w http.ResponseWriter, r *http.Request) {
	fileName := r.URL.Query().Get("fileName")
	if fileName == "" || strings.Contains(fileName, "..") {
		response.Warn(w, "文件名称不合法")
		return
	}
	path := filepath.Join(s.Config.DownloadPath, fileName)
	if _, err := os.Stat(path); err != nil {
		response.Warn(w, "文件不存在")
		return
	}
	w.Header().Set("Content-Disposition", "attachment; filename="+filepath.Base(fileName))
	http.ServeFile(w, r, path)
}

func (s *Server) CommonDownloadResource(w http.ResponseWriter, r *http.Request) {
	resource := strings.TrimSpace(r.URL.Query().Get("resource"))
	if resource == "" || strings.Contains(resource, "..") {
		response.Warn(w, "资源路径不合法")
		return
	}
	path := filepath.Join(s.Config.UploadPath, strings.TrimPrefix(resource, "/"))
	if _, err := os.Stat(path); err != nil {
		response.Warn(w, "文件不存在")
		return
	}
	w.Header().Set("Content-Disposition", "attachment; filename="+filepath.Base(path))
	http.ServeFile(w, r, path)
}

func joinURL(r *http.Request, path string) string {
	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}
	if fwd := r.Header.Get("X-Forwarded-Proto"); fwd != "" {
		scheme = fwd
	}
	host := r.Host
	if host == "" {
		host = "localhost"
	}
	return fmt.Sprintf("%s://%s/%s", scheme, host, strings.TrimPrefix(path, "/"))
}
