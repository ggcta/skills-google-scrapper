// Package model defines the on-disk entity shapes (Course, Path, Lab) so the Go
// tool reads and writes the exact same JSON as the Python reference version.
package model

import (
	"encoding/json"
	"strconv"
)

// FlexString unmarshals from either a JSON string or number, since ids have
// historically been stored both ways.
type FlexString string

func (f *FlexString) UnmarshalJSON(b []byte) error {
	if len(b) == 0 || string(b) == "null" {
		*f = ""
		return nil
	}
	if b[0] == '"' {
		var s string
		if err := json.Unmarshal(b, &s); err != nil {
			return err
		}
		*f = FlexString(s)
		return nil
	}
	// Number (or anything else) — keep the raw token trimmed of quotes.
	var n json.Number
	if err := json.Unmarshal(b, &n); err == nil {
		*f = FlexString(n.String())
		return nil
	}
	*f = FlexString(strconv.Quote(string(b)))
	return nil
}

func (f FlexString) MarshalJSON() ([]byte, error) { return json.Marshal(string(f)) }
func (f FlexString) String() string               { return string(f) }

// Course mirrors data/<portal>/courses/<id>.json.
type Course struct {
	ID           FlexString `json:"id"`
	Title        string     `json:"title"`
	Description  string     `json:"description"`
	DatePublished *string   `json:"datePublished,omitempty"` // pointer: nil = key absent
	Objectives   []string   `json:"objectives,omitempty"`
	Topics       *[]string  `json:"topics,omitempty"` // pointer: nil = key absent
	Modules      []Module   `json:"modules,omitempty"`
	Portal       string     `json:"portal,omitempty"`
	ScrapedTime  int64      `json:"scrapedTime,omitempty"`
}

// Module is one section of a course.
type Module struct {
	ID          FlexString `json:"id"`
	Title       string     `json:"title"`
	Description string     `json:"description"`
	Steps       []Step     `json:"steps"`
}

// Step groups activities within a module.
type Step struct {
	ID         FlexString `json:"id"`
	Prompt     *string    `json:"prompt"`
	IsOptional bool       `json:"isOptional"`
	Activities []Activity `json:"activities"`
}

// Activity is a single learning item (html_bundle, video, quiz, lab, ...).
type Activity struct {
	ID                FlexString `json:"id"`
	Href              string     `json:"href"`
	Title             string     `json:"title"`
	Description       *string    `json:"description"`
	Type              string     `json:"type"`
	IsComplete        bool       `json:"isComplete"`
	Link              string     `json:"link,omitempty"`
	Transcript        *string    `json:"transcript,omitempty"` // pointer: nil = key absent
	VideoID           string     `json:"videoId,omitempty"`
	QuizItems         []QuizItem `json:"quizItems,omitempty"`
	LocalDocumentPath string     `json:"local_document_path,omitempty"`
}

// QuizItem is one question in a quiz activity.
type QuizItem struct {
	Stem    string       `json:"stem"`
	Options []QuizOption `json:"options,omitempty"`
}

// QuizOption is one answer choice.
type QuizOption struct {
	Title string `json:"title"`
}

// Lab mirrors data/<portal>/labs/<id>.json. steps is an ordered {number: text}.
type Lab struct {
	ID          FlexString            `json:"id"`
	Title       string                `json:"title"`
	Description string                `json:"description"`
	Portal      string                `json:"portal,omitempty"`
	Steps       OrderedMap[string]    `json:"steps"`
	ScrapedTime int64                 `json:"scrapedTime,omitempty"`
}

// Path mirrors data/<portal>/paths/<id>.json. courses is an ordered map of refs.
type Path struct {
	ID            FlexString             `json:"id"`
	Title         string                 `json:"title"`
	Description   string                 `json:"description"`
	Portal        string                 `json:"portal,omitempty"`
	DatePublished *string                `json:"datePublished,omitempty"`
	Courses       OrderedMap[CourseRef]  `json:"courses"`
	ScrapedTime   int64                  `json:"scrapedTime,omitempty"`
}

// CourseRef is a path's reference to a course or lab activity.
type CourseRef struct {
	ID   string `json:"id"`
	Type string `json:"type"`
	Name string `json:"name"`
	URL  string `json:"url"`
}
