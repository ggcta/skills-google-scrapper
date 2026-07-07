package cli

import (
	"bufio"
	"fmt"
	"os"
	"strings"

	"csb/internal/portal"
)

// cmdInteractive runs a guided menu that dispatches to the same command
// handlers, with a persistent working portal (ports scraper.py).
func cmdInteractive(args []string) int {
	reader := bufio.NewReader(os.Stdin)
	working := portal.Default

	prompt := func(msg string) string {
		fmt.Print(msg)
		line, _ := reader.ReadString('\n')
		return strings.TrimSpace(line)
	}
	yesNo := func(msg string) bool {
		return strings.HasPrefix(strings.ToLower(prompt(msg+" [y/N]: ")), "y")
	}

	for {
		choice := strings.ToLower(prompt(fmt.Sprintf(
			"\nAVAILABLE OPTIONS  (working portal: %s)\n"+
				"  1. f: FETCH content (path / course / lab)\n"+
				"  2. l: LIST paths / courses / labs\n"+
				"  3. s: SEARCH the database\n"+
				"  4. m: GENERATE markdown\n"+
				"  5. w: LOGIN (sign in to the working portal)\n"+
				"  6. p: SWITCH portal (public / partner)\n"+
				"  0. q: QUIT\n"+
				"• PLEASE SELECT: ", working)))

		switch choice {
		case "0", "q":
			fmt.Println("Good day.")
			return 0
		case "6", "p":
			working = switchPortal(prompt, working)
		case "1", "f":
			interactiveFetch(prompt, yesNo, working)
		case "2", "l":
			interactiveList(prompt, yesNo, working)
		case "3", "s":
			interactiveSearch(prompt, working)
		case "4", "m":
			interactiveMD(prompt, yesNo, working)
		case "5", "w":
			cmdLogin([]string{"--portal", working})
		case "":
			// ignore empty input
		default:
			fmt.Printf("[INVALID CHOICE] %s\n", choice)
		}
	}
}

func switchPortal(prompt func(string) string, current string) string {
	choice := strings.ToLower(prompt("Select working portal:\n  a. public\n  b. partner\n• Select: "))
	switch choice {
	case "a", "public":
		fmt.Println("Working portal set to: public")
		return "public"
	case "b", "partner":
		fmt.Println("Working portal set to: partner")
		return "partner"
	}
	fmt.Printf("Portal unchanged (still %s).\n", current)
	return current
}

func portalFlag(working string) string {
	if working == "partner" {
		return "-B"
	}
	return "-A"
}

func interactiveFetch(prompt func(string) string, yesNo func(string) bool, working string) {
	kind := strings.ToLower(prompt("Fetch what? [p]ath / [c]ourse / [l]ab / [b]ack: "))
	flag := map[string]string{"p": "-p", "c": "-c", "l": "-l"}[kind]
	if flag == "" {
		return
	}
	ids := prompt("• Enter ID(s) or URL(s) (space/comma separated): ")
	if strings.TrimSpace(ids) == "" {
		fmt.Println("No IDs provided. Cancelled.")
		return
	}
	args := []string{portalFlag(working), flag}
	args = append(args, splitIDs(ids)...)
	if yesNo("Force re-fetch items that already exist?") {
		args = append(args, "--force")
	}
	depth := strings.ToLower(prompt("Content depth? [F]ull (default) / [t]oc only / full but [n]o transcripts: "))
	switch depth {
	case "t", "toc":
		args = append(args, "--toc")
	case "n", "no", "no-transcript":
		args = append(args, "--no-transcript")
	}
	if yesNo("Skip generating markdown files?") {
		args = append(args, "--no-md")
	}
	cmdFetch(args)
}

func interactiveList(prompt func(string) string, yesNo func(string) bool, working string) {
	kind := strings.ToLower(prompt("List what? [p]aths / [c]ourses / [l]abs: "))
	flag := map[string]string{"p": "--paths", "c": "--courses", "l": "--labs"}[kind]
	if flag == "" {
		return
	}
	args := []string{portalFlag(working), flag}
	if yesNo("Reload from the website first?") {
		args = append(args, "--reload")
	}
	if yesNo("Sort by ID (instead of name)?") {
		args = append(args, "--id")
	}
	cmdList(args)
}

func interactiveSearch(prompt func(string) string, working string) {
	query := prompt("• Search query: ")
	if strings.TrimSpace(query) == "" {
		fmt.Println("Empty query. Cancelled.")
		return
	}
	args := []string{portalFlag(working), query}
	kind := strings.ToLower(prompt("Limit to type? [a]ll / [p]ath / [c]ourse / [l]ab (default all): "))
	if f, ok := map[string]string{"p": "--path", "c": "--course", "l": "--lab"}[kind]; ok {
		args = append(args, f)
	}
	cmdSearch(args)
}

func interactiveMD(prompt func(string) string, yesNo func(string) bool, working string) {
	kind := strings.ToLower(prompt("Generate markdown for? [p]ath / [c]ourse / [l]ab: "))
	flag := map[string]string{"p": "-p", "c": "-c", "l": "-l"}[kind]
	if flag == "" {
		return
	}
	ids := prompt("• Enter ID(s) (space/comma separated): ")
	if strings.TrimSpace(ids) == "" {
		fmt.Println("No IDs provided. Cancelled.")
		return
	}
	args := []string{portalFlag(working), flag, strings.Join(splitIDs(ids), ",")}
	if yesNo("Table of contents only?") {
		args = append(args, "--toc")
	}
	cmdMD(args)
}
