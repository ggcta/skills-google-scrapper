// Command csb is a Go reimplementation of the Cloud Skills Boost scraper.
// It reads and writes the same data/ and csbmdvault/ layout as the Python
// reference version, so the two can be used interchangeably during migration.
package main

import (
	"os"

	"csb/internal/cli"
)

func main() {
	os.Exit(cli.Run(os.Args[1:]))
}
