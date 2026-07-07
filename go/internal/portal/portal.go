// Package portal holds the multi-portal registry. The same content is served
// from two independent portals with SEPARATE id sequences (e.g. partner path 85
// == public path 16), so an entity's true identity is the pair (portal, id).
// Each portal is scoped to its own storage root so the two catalogs can never
// overwrite each other.
package portal

import (
	"net/url"
	"strings"
)

// Default is the portal assumed when none is specified.
const Default = "public"

// Config is the set of URLs for a single portal.
type Config struct {
	Host       string
	Base       string
	Paths      string
	Courses    string
	Lab        string
	APIPaths   string
	APICourses string
	APILabs    string
}

// Registry maps a portal key to its URL configuration.
var Registry = map[string]Config{
	"public": {
		Host:       "www.skills.google",
		Base:       "https://www.skills.google",
		Paths:      "https://www.skills.google/paths",
		Courses:    "https://www.skills.google/course_templates",
		Lab:        "https://www.skills.google/catalog_lab",
		APIPaths:   "https://www.skills.google/catalog/list?format%5B%5D=learning_plans",
		APICourses: "https://www.skills.google/catalog/list?format%5B%5D=courses",
		APILabs:    "https://www.skills.google/catalog/list?format%5B%5D=labs",
	},
	"partner": {
		Host:       "partner.skills.google",
		Base:       "https://partner.skills.google",
		Paths:      "https://partner.skills.google/paths",
		Courses:    "https://partner.skills.google/course_templates",
		Lab:        "https://partner.skills.google/catalog_lab",
		APIPaths:   "https://partner.skills.google/catalog/list?format%5B%5D=learning_plans",
		APICourses: "https://partner.skills.google/catalog/list?format%5B%5D=courses",
		APILabs:    "https://partner.skills.google/catalog/list?format%5B%5D=labs",
	},
}

// Keys returns the registered portal names in a stable order.
func Keys() []string {
	return []string{"public", "partner"}
}

// Get returns the config for a portal, falling back to the default.
func Get(p string) Config {
	if cfg, ok := Registry[p]; ok {
		return cfg
	}
	return Registry[Default]
}

// Valid reports whether p names a known portal.
func Valid(p string) bool {
	_, ok := Registry[p]
	return ok
}

// FromHost maps a hostname to a portal key, defaulting to the public portal.
func FromHost(host string) string {
	host = strings.ToLower(host)
	for _, p := range Keys() {
		if strings.Contains(host, Registry[p].Host) {
			return p
		}
	}
	return Default
}

// AndID resolves a fetch target into a (portal, id) pair.
//
// It accepts either a bare id ("53") or a full URL
// ("https://partner.skills.google/paths/85"). For a URL the portal is inferred
// from the host and the id is the last path segment. For a bare id the portal is
// returned as "" so the caller can apply its own default.
func AndID(value string) (portalKey, id string) {
	if value == "" {
		return "", value
	}

	looksLikeURL := strings.Contains(value, "://") ||
		strings.Contains(strings.ToLower(value), "skills.google")
	if !looksLikeURL {
		return "", strings.TrimSpace(value)
	}

	raw := value
	if !strings.Contains(raw, "://") {
		raw = "https://" + raw
	}
	parsed, err := url.Parse(raw)
	if err != nil {
		return "", strings.TrimSpace(value)
	}
	p := FromHost(parsed.Host)
	segments := []string{}
	for _, seg := range strings.Split(parsed.Path, "/") {
		if seg != "" {
			segments = append(segments, seg)
		}
	}
	if len(segments) == 0 {
		return p, ""
	}
	return p, segments[len(segments)-1]
}
