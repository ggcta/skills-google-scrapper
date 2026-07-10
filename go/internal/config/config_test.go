package config

import "testing"

// TestResolvePrecedence checks env > config value > default.
func TestResolvePrecedence(t *testing.T) {
	t.Setenv("CSB_TEST_KEY", "from-env")
	if got := Resolve("CSB_TEST_KEY", "from-config", "from-default"); got != "from-env" {
		t.Fatalf("env should win: got %q", got)
	}
	t.Setenv("CSB_TEST_KEY", "") // empty env == unset
	if got := Resolve("CSB_TEST_KEY", "from-config", "from-default"); got != "from-config" {
		t.Fatalf("config should win over default: got %q", got)
	}
	if got := Resolve("CSB_UNSET_KEY", "", "from-default"); got != "from-default" {
		t.Fatalf("default should apply: got %q", got)
	}
}
