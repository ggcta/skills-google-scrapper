// Package config loads optional user preferences from a YAML file that override
// the built-in defaults, without anyone having to edit source. It mirrors the
// Python app/config layer so the Go and Python tools honour the same file.
//
// Precedence for any setting is: environment variable > config.yaml > built-in
// default (CLI flags, handled by the commands, win over all of these).
//
// The file is looked up (first match wins) at:
//   - $CSB_CONFIG (explicit path)
//   - ./config.yaml
//   - ./config/config.yaml
//
// relative to the working directory. All keys are optional.
package config

import (
	"os"
	"path/filepath"
	"sync"

	"gopkg.in/yaml.v3"
)

// Config is the user-overridable settings. Zero values mean "unset" (fall back
// to the default), so every field is a plain string.
type Config struct {
	Paths struct {
		Data    string `yaml:"data"`    // JSON backups + TinyDB database
		Vault   string `yaml:"vault"`   // Markdown output (open in Obsidian)
		Logs    string `yaml:"logs"`    // per-run activity logs
		Profile string `yaml:"profile"` // reusable Chrome sign-in profile
		Themes  string `yaml:"themes"`  // PDF theme folder (backlog #5)
	} `yaml:"paths"`
	Portal string `yaml:"portal"` // default portal: public | partner
}

var (
	once   sync.Once
	loaded Config
	path   string
)

// Get returns the loaded config, reading the file once on first use. A missing
// or malformed file is treated as "no overrides" (all fields empty).
func Get() Config {
	once.Do(load)
	return loaded
}

// Path returns the config file that was loaded, or "" if none was found.
func Path() string {
	once.Do(load)
	return path
}

func load() {
	path = locate()
	if path == "" {
		return
	}
	b, err := os.ReadFile(path)
	if err != nil {
		path = ""
		return
	}
	// Best-effort: keep whatever parses; unknown keys are ignored.
	_ = yaml.Unmarshal(b, &loaded)
}

func locate() string {
	if p := os.Getenv("CSB_CONFIG"); p != "" {
		return p
	}
	for _, c := range []string{"config.yaml", filepath.Join("config", "config.yaml")} {
		if info, err := os.Stat(c); err == nil && !info.IsDir() {
			return c
		}
	}
	return ""
}

// Resolve applies the standard precedence for a single string setting:
// the environment variable (if set) wins, else the config value (if non-empty),
// else the built-in default.
func Resolve(envKey, configValue, def string) string {
	if v := os.Getenv(envKey); v != "" {
		return v
	}
	if configValue != "" {
		return configValue
	}
	return def
}
