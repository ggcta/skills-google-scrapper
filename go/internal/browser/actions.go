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
// pulls external Rise/Storage lesson content. Bounded by NavTimeout.
func (s *Session) EvalAsync(expr string, out any) error {
	return s.run(NavTimeout,
		chromedp.Evaluate(expr, out, func(p *runtime.EvaluateParams) *runtime.EvaluateParams {
			return p.WithAwaitPromise(true)
		}),
	)
}

// Cookies returns all browser cookies (used to authenticate document downloads,
// mirroring the Python requests-with-driver-cookies approach).
func (s *Session) Cookies() ([]*network.Cookie, error) {
	var cookies []*network.Cookie
	err := s.run(15*time.Second, chromedp.ActionFunc(func(ctx context.Context) error {
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
	_ = s.run(8*time.Second,
		chromedp.Click("a.start-button.button.button--positive", chromedp.ByQuery),
		chromedp.WaitReady("ql-quiz", chromedp.ByQuery),
	)
}

// PageHTML returns the current page's HTML without navigating.
func (s *Session) PageHTML() (string, error) {
	var html string
	err := s.run(15*time.Second, chromedp.OuterHTML("html", &html, chromedp.ByQuery))
	return html, err
}

// FetchText navigates to url and returns document.body.innerText — used for the
// catalog list API endpoints, which render raw JSON in the page body. Like
// Navigate, it is bounded by NavTimeout and relaunches a dead session once.
func (s *Session) FetchText(url string) (string, error) {
	var text string
	err := s.withConnRetry(func() error {
		text = ""
		return s.fetchTextOnce(url, &text)
	})
	return text, err
}

// fetchTextOnce performs a single FetchText attempt (with the dead-session
// relaunch retry), leaving lost-connection retrying to withConnRetry.
func (s *Session) fetchTextOnce(url string, text *string) error {
	var err error
	for attempt := 0; attempt < 2; attempt++ {
		if !s.alive() {
			if rerr := s.relaunch(); rerr != nil {
				return rerr
			}
		}
		ctx, cancel := context.WithTimeout(s.Ctx, NavTimeout)
		err = chromedp.Run(ctx,
			chromedp.Navigate(url),
			chromedp.WaitReady("body", chromedp.ByQuery),
			chromedp.Evaluate(`document.body.innerText`, text),
		)
		cancel()
		if err == nil {
			return nil
		}
		if !s.alive() && attempt == 0 {
			continue
		}
		return err
	}
	return err
}
