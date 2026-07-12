package store

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// Items management (backlog #17): delete and rename stored items. The SSOT model
// (#9) spreads an item across the database.json ledger row, a per-item JSON file,
// and generated vault .md/.pdf; these primitives let the `db` command remove or
// rename all of them consistently. A bogus catalog stub (a ledger row with no
// per-item file) is handled cleanly — only its row is removed.

// ItemJSONPath returns the per-item JSON path (data/<portal>/<table>/<id>.json).
func ItemJSONPath(portalKey, table, id string) string {
	return jsonPath(portalKey, table, id)
}

// MaterialsDir returns the shared materials folder for an item
// (<vault>/materials/<table>/<id>). Materials are keyed globally by id, so this
// path is portal-agnostic.
func MaterialsDir(table, id string) string {
	return filepath.Join(VaultRoot(), "materials", table, id)
}

// RowExists reports whether a ledger row with the given id exists in a table.
func RowExists(portalKey, table, id string) bool {
	docs, _ := LoadTable(portalKey, table)
	for _, d := range docs {
		if d.ID() == id {
			return true
		}
	}
	return false
}

// DeleteLedgerRow removes the row whose "id" matches from a database.json table,
// preserving all other tables and rows. Returns whether a row was removed.
func DeleteLedgerRow(portalKey, table, id string) (bool, error) {
	path := dbPath(portalKey)
	b, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return false, nil
		}
		return false, err
	}
	var root map[string]map[string]map[string]any
	if err := json.Unmarshal(b, &root); err != nil {
		return false, err
	}
	tbl, ok := root[table]
	if !ok {
		return false, nil
	}
	removed := false
	for k, d := range tbl {
		if fmt.Sprint(d["id"]) == id {
			delete(tbl, k)
			removed = true
		}
	}
	if !removed {
		return false, nil
	}
	out, err := json.MarshalIndent(root, "", "  ")
	if err != nil {
		return false, err
	}
	return true, writeFile(path, out)
}

// SetItemName renames an item: it updates the per-item JSON "title" (when the
// file exists) and the ledger row's name/title. It returns the item's OLD vault
// .md path so the caller can drop the now-stale .md/.pdf (their filename is
// derived from the title); the path is "" when there is no per-item file.
func SetItemName(portalKey, table, id, newName string) (oldMdPath string, err error) {
	jp := jsonPath(portalKey, table, id)
	if b, rerr := os.ReadFile(jp); rerr == nil {
		var obj map[string]any
		if err := json.Unmarshal(b, &obj); err != nil {
			return "", err
		}
		if oldTitle, _ := obj["title"].(string); oldTitle != "" {
			p := mdPath(portalKey, table, oldTitle)
			if abs, aerr := filepath.Abs(p); aerr == nil {
				p = abs
			}
			oldMdPath = p
		}
		obj["title"] = newName
		out, merr := json.MarshalIndent(obj, "", "  ")
		if merr != nil {
			return "", merr
		}
		if werr := writeFile(jp, append(out, '\n')); werr != nil {
			return "", werr
		}
	} else if !os.IsNotExist(rerr) {
		return "", rerr
	}
	// Update (or create) the ledger row so browse/search reflect the new name.
	err = UpsertDoc(portalKey, table, map[string]any{
		"id":     id,
		"name":   newName,
		"title":  newName,
		"type":   typeName[table],
		"portal": portalKey,
	})
	return oldMdPath, err
}
