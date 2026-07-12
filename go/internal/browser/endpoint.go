package browser

import (
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Backlog #13: a persistent "browser" process advertises its Chrome remote-
// debugging endpoint here so separate skills-scraper runs (fetch/sync) can
// connect to the SAME already-signed-in Chrome instead of launching their own
// (which the site would re-challenge for sign-in). The file is runtime-only —
// written when the persistent browser starts, removed when it exits.

// endpoint is the advertised reuse target.
type endpoint struct {
	WS   string `json:"ws"`
	Port int    `json:"port"`
	PID  int    `json:"pid"`
}

// endpointFile lives next to the shared profile dir, so it is naturally scoped to
// the same machine/profile the browser uses.
func endpointFile() string {
	dir := DefaultProfileDir()
	if dir == "" {
		return ".csb-browser.json"
	}
	if abs, err := filepath.Abs(dir); err == nil {
		dir = abs
	}
	return filepath.Join(filepath.Dir(dir), ".csb-browser.json")
}

// FreePort returns an available localhost TCP port for Chrome's debug endpoint.
func FreePort() (int, error) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, err
	}
	defer l.Close()
	return l.Addr().(*net.TCPAddr).Port, nil
}

// SaveEndpoint records the running persistent browser's debug port for reuse.
func SaveEndpoint(port int) error {
	ep := endpoint{
		WS:   fmt.Sprintf("ws://127.0.0.1:%d", port),
		Port: port,
		PID:  os.Getpid(),
	}
	b, err := json.MarshalIndent(ep, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(endpointFile(), append(b, '\n'), 0o644)
}

// LoadEndpoint returns the advertised reuse websocket URL, if a persistent
// browser has advertised one.
func LoadEndpoint() (ws string, ok bool) {
	b, err := os.ReadFile(endpointFile())
	if err != nil {
		return "", false
	}
	var ep endpoint
	if json.Unmarshal(b, &ep) != nil || ep.WS == "" {
		return "", false
	}
	return ep.WS, true
}

// EndpointAlive reports whether a browser is actually listening at ws, via a
// short HTTP probe of /json/version, so a stale endpoint file never causes a
// hang or a connect to nothing.
func EndpointAlive(ws string) bool {
	host := strings.TrimPrefix(ws, "ws://")
	host = strings.TrimPrefix(host, "wss://")
	if i := strings.IndexByte(host, '/'); i >= 0 {
		host = host[:i]
	}
	client := http.Client{Timeout: 800 * time.Millisecond}
	resp, err := client.Get("http://" + host + "/json/version")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

// ClearEndpoint removes the endpoint file when the persistent browser exits.
func ClearEndpoint() { _ = os.Remove(endpointFile()) }
