package ws

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/gorilla/websocket"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/scheduler"
)

const (
	minIntervalSeconds     = 3
	maxIntervalSeconds     = 30
	defaultIntervalSeconds = 5
	authFrameTimeout       = 5 * time.Second
	closeAuthCode          = 4401
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin:     func(r *http.Request) bool { return true },
}

type JobsGateway struct {
	Auth      *auth.Service
	Scheduler *scheduler.Runtime
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

func (g *JobsGateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("jobs ws upgrade: %v", err)
		return
	}
	defer conn.Close()

	writer := &connWriter{conn: conn}
	if !g.authorize(r.Context(), writer, r) {
		writer.closeAuth()
		return
	}

	interval := normalizeInterval(r.URL.Query().Get("interval"))
	log.Printf("[jobs-ws] connected interval=%ds", interval)
	for {
		if err := writer.writeJSON(scheduler.JobsLiteSnapshot(r.Context(), g.Scheduler)); err != nil {
			return
		}
		if !waitInterval(conn, writer, interval) {
			return
		}
	}
}

func (g *JobsGateway) authorize(ctx context.Context, writer *connWriter, r *http.Request) bool {
	if cookie, err := r.Cookie("Admin-Token"); err == nil && cookie.Value != "" {
		return g.Auth.VerifySession(ctx, cookie.Value) == nil
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
	return g.Auth.VerifySession(ctx, token) == nil
}

func tokenFromAuthFrame(raw string) string {
	var data map[string]interface{}
	if err := json.Unmarshal([]byte(raw), &data); err != nil {
		return ""
	}
	if data["type"] != "auth" {
		return ""
	}
	token, _ := data["token"].(string)
	return token
}

func normalizeInterval(raw string) int {
	if raw == "" {
		return defaultIntervalSeconds
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return defaultIntervalSeconds
	}
	if value < minIntervalSeconds {
		return minIntervalSeconds
	}
	if value > maxIntervalSeconds {
		return maxIntervalSeconds
	}
	return value
}

func waitInterval(conn *websocket.Conn, writer *connWriter, seconds int) bool {
	deadline := time.Now().Add(time.Duration(seconds) * time.Second)
	for time.Now().Before(deadline) {
		remaining := time.Until(deadline)
		_ = conn.SetReadDeadline(time.Now().Add(remaining))
		_, msg, err := conn.ReadMessage()
		_ = conn.SetReadDeadline(time.Time{})
		if err != nil {
			if websocket.IsCloseError(err, websocket.CloseNormalClosure, websocket.CloseGoingAway) {
				return false
			}
			if ne, ok := err.(interface{ Timeout() bool }); ok && ne.Timeout() {
				return true
			}
			return false
		}
		if string(msg) == "ping" {
			if err := writer.writeText("pong"); err != nil {
				return false
			}
		}
	}
	return true
}
