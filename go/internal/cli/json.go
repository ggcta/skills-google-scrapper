package cli

import (
	"encoding/json"
	"os"
)

// jsonItem is a structured list/search row for GUI/scripting consumers.
type jsonItem struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Type   string `json:"type"`
	Portal string `json:"portal"`
}

// emitJSON writes v as indented JSON to stdout (the machine-readable channel).
func emitJSON(v any) {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(v)
}
