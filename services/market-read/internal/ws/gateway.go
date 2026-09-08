// Package ws implements WS /ws/market/quotes with the Python FE contract.
package ws

import (
	"context"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"

	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/quotes"
)

const (
	authFrameTimeout = 5 * time.Second
	closeAuthCode    = 4401
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin:     func(r *http.Request) bool { return true },
}

type Gateway struct {
	Auth   *auth.Authenticator
	Quotes *quotes.Service
}

type connWriter struct {
	mu   sync.Mutex
	conn *websocket.Conn
}

func (w *connWriter) writeJSON(v interface{}) error {
	w.mu.Lock()
	defer w.mu.Unlock()
	return w.conn.WriteJSON(v)
}

func (w *connWriter) writeText(s string) error {
	w.mu.Lock()
	defer w.mu.Unlock()
	return w.conn.WriteMessage(websocket.TextMessage, []byte(s))
}

func (w *connWriter) closeAuth() {
	w.mu.Lock()
	defer w.mu.Unlock()
	_ = w.conn.WriteControl(
		websocket.CloseMessage,
		websocket.FormatCloseMessage(closeAuthCode, "未授权"),
		time.Now().Add(time.Second),
	)
}

func (g *Gateway) ServeMarketQuotes(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("ws upgrade: %v", err)
		return
	}
	defer conn.Close()

	writer := &connWriter{conn: conn}
	if !g.authorize(r.Context(), writer, r) {
		writer.closeAuth()
		return
	}

	interval := NormalizeInterval(r.URL.Query().Get("interval"))
	incoming := make(chan clientFrame, 8)
	go readLoop(conn, incoming)

	subscribed := []quotes.Pair{}
	reason := "interval"
	log.Printf("market-ws connected interval=%ds", interval)
	for {
		if reason == "closed" {
			return
		}
		if reason == "interval" {
			if err := writer.writeJSON(g.indexPayload(r.Context())); err != nil {
				return
			}
		}
		if len(subscribed) > 0 {
			if err := writer.writeJSON(g.quotesPayload(r.Context(), subscribed)); err != nil {
				return
			}
		}
		reason = waitInterval(incoming, interval, writer, &subscribed)
		if reason == "quote" && len(subscribed) == 0 {
			reason = "interval"
		}
	}
}

func (g *Gateway) authorize(ctx context.Context, writer *connWriter, r *http.Request) bool {
	if cookie, err := r.Cookie("Admin-Token"); err == nil && cookie.Value != "" {
		_, err := g.Auth.VerifySession(ctx, cookie.Value)
		return err == nil
	}
	_ = writer.conn.SetReadDeadline(time.Now().Add(authFrameTimeout))
	_, raw, err := writer.conn.ReadMessage()
	_ = writer.conn.SetReadDeadline(time.Time{})
	if err != nil {
		return false
	}
	token := tokenFromAuthFrame(string(raw))
	if token == "" {
		return false
	}
	_, err = g.Auth.VerifySession(ctx, token)
	return err == nil
}

func readLoop(conn *websocket.Conn, out chan<- clientFrame) {
	defer close(out)
	for {
		_, raw, err := conn.ReadMessage()
		if err != nil {
			return
		}
		frame := parseClientFrame(string(raw))
		select {
		case out <- frame:
		default:
		}
	}
}

func waitInterval(incoming <-chan clientFrame, seconds int, writer *connWriter, subscribed *[]quotes.Pair) string {
	remaining := time.Duration(seconds) * time.Second
	for remaining > 0 {
		started := time.Now()
		timer := time.NewTimer(remaining)
		select {
		case frame, ok := <-incoming:
			timer.Stop()
			if !ok {
				return "closed"
			}
			if handleFrame(frame, writer, subscribed) == "quote" {
				return "quote"
			}
			remaining -= time.Since(started)
		case <-timer.C:
			return "interval"
		}
	}
	return "interval"
}

func handleFrame(frame clientFrame, writer *connWriter, subscribed *[]quotes.Pair) string {
	switch frame.Kind {
	case kindPing:
		_ = writer.writeText("pong")
	case kindSubscribe:
		*subscribed = append([]quotes.Pair(nil), frame.Symbols...)
		return "quote"
	case kindUnsubscribe:
		if len(frame.Symbols) == 0 {
			*subscribed = []quotes.Pair{}
			return ""
		}
		drop := map[string]bool{}
		for _, p := range frame.Symbols {
			drop[p.Key()] = true
		}
		kept := make([]quotes.Pair, 0, len(*subscribed))
		for _, p := range *subscribed {
			if !drop[p.Key()] {
				kept = append(kept, p)
			}
		}
		*subscribed = kept
	}
	return ""
}

func (g *Gateway) indexPayload(ctx context.Context) map[string]interface{} {
	data := map[string]interface{}{"items": []interface{}{}, "asOf": nil, "cached": false}
	if g.Quotes != nil {
		data = g.Quotes.IndexQuotes(ctx)
	}
	return map[string]interface{}{
		"code":    200,
		"msg":     "操作成功",
		"channel": "index",
		"data":    data,
	}
}

func (g *Gateway) quotesPayload(ctx context.Context, pairs []quotes.Pair) map[string]interface{} {
	data := map[string]interface{}{"items": []interface{}{}, "asOf": nil, "source": "empty", "cached": false}
	if g.Quotes != nil {
		data = g.Quotes.LiveQuotes(ctx, pairs)
	}
	return map[string]interface{}{
		"code":    200,
		"msg":     "操作成功",
		"channel": "quotes",
		"quotes":  data,
	}
}
