package browser

import (
	"context"
	"time"

	"github.com/chromedp/cdproto/network"
	"github.com/chromedp/cdproto/runtime"
	"github.com/chromedp/chromedp"
)

// EvalAsync evaluates a JavaScript expression that resolves to a Promise and
// unmarshals the resolved value into out. Used for the __fetchCourse() call that
// pulls external Rise/Storage lesson content.
func (s *Session) EvalAsync(expr string, out any) error {
	return chromedp.Run(s.Ctx,
		chromedp.Evaluate(expr, out, func(p *runtime.EvaluateParams) *runtime.EvaluateParams {
			return p.WithAwaitPromise(true)
		}),
	)
}

// Cookies returns all browser cookies (used to authenticate document downloads,
// mirroring the Python requests-with-driver-cookies approach).
func (s *Session) Cookies() ([]*network.Cookie, error) {
	var cookies []*network.Cookie
	err := chromedp.Run(s.Ctx, chromedp.ActionFunc(func(ctx context.Context) error {
		var e error
		cookies, e = network.GetCookies().Do(ctx)
		return e
	}))
	return cookies, err
}

// ClickStartQuiz best-effort clicks the "Start Quiz" button if present and waits
// for the quiz element (mirrors process_quiz). A missing button just times out
// quietly and is not treated as an error.
func (s *Session) ClickStartQuiz() {
	ctx, cancel := context.WithTimeout(s.Ctx, 8*time.Second)
	defer cancel()
	_ = chromedp.Run(ctx,
		chromedp.Click("a.start-button.button.button--positive", chromedp.ByQuery),
		chromedp.WaitReady("ql-quiz", chromedp.ByQuery),
	)
}

// PageHTML returns the current page's HTML without navigating.
func (s *Session) PageHTML() (string, error) {
	var html string
	err := chromedp.Run(s.Ctx, chromedp.OuterHTML("html", &html, chromedp.ByQuery))
	return html, err
}
