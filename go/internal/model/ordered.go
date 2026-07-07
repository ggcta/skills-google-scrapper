package model

import (
	"bytes"
	"encoding/json"
)

// OrderedMap is a JSON object that preserves key insertion order on decode and
// re-encode. The Python version relies on dict ordering (path.courses,
// lab.steps) when generating Markdown, so we must preserve it to match output.
type OrderedMap[V any] struct {
	Keys   []string
	Values map[string]V
}

// Get returns the value for a key.
func (m *OrderedMap[V]) Get(k string) (V, bool) {
	v, ok := m.Values[k]
	return v, ok
}

// Len reports the number of entries.
func (m *OrderedMap[V]) Len() int { return len(m.Keys) }

// Set inserts or updates a key, preserving first-insertion order.
func (m *OrderedMap[V]) Set(k string, v V) {
	if m.Values == nil {
		m.Values = map[string]V{}
	}
	if _, exists := m.Values[k]; !exists {
		m.Keys = append(m.Keys, k)
	}
	m.Values[k] = v
}

// UnmarshalJSON decodes a JSON object while preserving key order.
func (m *OrderedMap[V]) UnmarshalJSON(data []byte) error {
	m.Keys = nil
	m.Values = map[string]V{}

	dec := json.NewDecoder(bytes.NewReader(data))
	// Opening '{'
	tok, err := dec.Token()
	if err != nil {
		return err
	}
	if d, ok := tok.(json.Delim); !ok || d != '{' {
		// Not an object (e.g. null) — leave empty.
		return nil
	}
	for dec.More() {
		keyTok, err := dec.Token()
		if err != nil {
			return err
		}
		key := keyTok.(string)
		var val V
		if err := dec.Decode(&val); err != nil {
			return err
		}
		m.Keys = append(m.Keys, key)
		m.Values[key] = val
	}
	// Closing '}'
	_, err = dec.Token()
	return err
}

// MarshalJSON encodes the object in stored key order.
func (m OrderedMap[V]) MarshalJSON() ([]byte, error) {
	var buf bytes.Buffer
	buf.WriteByte('{')
	for i, k := range m.Keys {
		if i > 0 {
			buf.WriteByte(',')
		}
		kb, err := json.Marshal(k)
		if err != nil {
			return nil, err
		}
		buf.Write(kb)
		buf.WriteByte(':')
		vb, err := json.Marshal(m.Values[k])
		if err != nil {
			return nil, err
		}
		buf.Write(vb)
	}
	buf.WriteByte('}')
	return buf.Bytes(), nil
}
