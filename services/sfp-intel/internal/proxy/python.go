package proxy

import (
	"io"
	"net/http"
	"net/url"
	"strings"
)

type PythonIntel struct {
	base *url.URL
	cli  *http.Client
}

func NewPythonIntel(raw string) (*PythonIntel, error) {
	u, err := url.Parse(strings.TrimRight(raw, "/"))
	if err != nil {
		return nil, err
	}
	return &PythonIntel{
		base: u,
		cli:  &http.Client{},
	}, nil
}

func (p *PythonIntel) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	target := *p.base
	target.Path = singleJoin(p.base.Path, r.URL.Path)
	target.RawQuery = r.URL.RawQuery
	req, err := http.NewRequestWithContext(r.Context(), r.Method, target.String(), r.Body)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}
	copyHeader(req.Header, r.Header)
	resp, err := p.cli.Do(req)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()
	copyHeader(w.Header(), resp.Header)
	w.WriteHeader(resp.StatusCode)
	_, _ = io.Copy(w, resp.Body)
}

func copyHeader(dst, src http.Header) {
	for k, vv := range src {
		for _, v := range vv {
			dst.Add(k, v)
		}
	}
}

func singleJoin(a, b string) string {
	as := strings.TrimRight(a, "/")
	bs := strings.TrimLeft(b, "/")
	switch {
	case as == "":
		return "/" + bs
	case bs == "":
		return as
	default:
		return as + "/" + bs
	}
}
