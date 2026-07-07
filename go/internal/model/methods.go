package model

import "csb/internal/portal"

// PortalKey returns the entity's portal, defaulting to public when unset (legacy
// records predate the portal field).
func (c *Course) PortalKey() string { return portalOr(c.Portal) }
func (p *Path) PortalKey() string   { return portalOr(p.Portal) }
func (l *Lab) PortalKey() string    { return portalOr(l.Portal) }

func portalOr(p string) string {
	if p == "" {
		return portal.Default
	}
	return p
}

// URL computes the canonical portal URL for the entity (matches the Python
// url @property used in front matter and headings).
func (c *Course) URL() string { return portal.Get(c.PortalKey()).Courses + "/" + c.ID.String() }
func (p *Path) URL() string   { return portal.Get(p.PortalKey()).Paths + "/" + p.ID.String() }
func (l *Lab) URL() string    { return portal.Get(l.PortalKey()).Lab + "/" + l.ID.String() }

// BaseURL is the portal root, e.g. https://partner.skills.google.
func (c *Course) BaseURL() string { return portal.Get(c.PortalKey()).Base }
