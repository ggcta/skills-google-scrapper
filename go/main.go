// Command skills-scraper (Google Skills Scraper) is a Go reimplementation of the
// scraper. It reads and writes the same data/ and csbmdvault/ layout as the
// Python reference version, so the two can be used interchangeably.
package main

import (
	"os"

	"csb/internal/cli"
)

func main() {
	os.Exit(cli.Run(os.Args[1:]))
}
