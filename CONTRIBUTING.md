# CONTRIBUTION

Every contribution is very much welcomed!

## Project Overview

- A Google Skills Scrapper.
- The original code base was built in Python #A.
- The current code base is developed in Go #B for the core and with Tauri for the GUI #C.
- For every change made to either the #A or #B or #C, ensure to cascade the change to the other components.

## Principles

- Keep it simple, stupid (KISS).
- No magic, no hidden side effects.
- Plain and simple.

## Coding Guidelines

- Always use Linux line endings (LF), NO QUESTION!
- Always use Spaces instead of Tabs for indentation.
- Always Trim Trailing Whitespace (configure your editor accordingly).
- Always use EOF delimiters (the 1 extra empty line or `\n` at the end of the file).
- DO NOT USE MULTIPLE STATEMENTS for a single line.
- Markdown: DO NOT USE MULTIPLE LINES for a single paragraph or block of text.

`.gitattributes`:

```yaml
# Auto detect text files and perform LF normalization
* text=auto eol=lf

```

Sublime Text sample:

```json
{
  "default_line_ending": "unix",
  "translate_tabs_to_spaces": true,
  "draw_white_space": ["all_tabs", "selection", "trailing", "isolated"],
  "trim_automatic_white_space": true,
  "show_line_endings": true,
  // Not a must but recommended, utf-8 everywhere
  "show_encoding": true,
}

```

## Components

- core:
  - `app/`, Python: the very first version, supports both CLI and Interactive modes.
  - `go/`, Go: the Go version of the CLI, supports both CLI and Interactive modes.
- gui:
  - `gui/`, Rust/Tauri: the graphical user interface, targets non-development users.

## Backglog

### Rules

> [!important]
> - severity: `#cri`(tical), `#hig`(h), `#med`(ium)
> - category: `#ftr`, `#fix`, `#rfr`(refactor), `#enh`(ancement)
> - components:
>    - `cor`(e): all the components or core engine (Go/Python)
>    - `cli`: the CLI components (Go/Python)
>    - `gui`: the graphical user interface (Rust/Tauri)

### Backlog

- [x] #cri #cor #ftr #1 Shut down the browser session gracefully, even when the application (gui/cli) is terminated.
- [x] #hig #cor #ftr #2 Allow to login/open the browser, and then re-use the browser session for subsequent requests (fetching).
- [x] #hig #cor #ftr #3 Handle `https://www.skills.google/users/sign_in` if the user is not already signed in.
- [x] #hig #gui #ftr #4 The GUI is freezing when some browser-activity is performed. Decouple browser-activity from the GUI thread.
- [x] #med #cor #ftr #5 MD to PDF conversion with styles using [Typst](https://typst.app). Go core + GUI: a `pdf` command (on-demand `-p/-c/-l <ids>`, batch cascade like `fetch`, `--theme`, warns when an item isn't fully fetched) rendering via `pandoc --pdf-engine=typst` with selectable themes under `theme/<name>/` (flagship `humanist`); the GUI Browse tab gains a theme picker + 'Generate PDF'. Python parity is #15.
- [x] #hig #cor #ftr #6 Check an item's completeness in case users interupts the fetching process before starting a fetch or finishing it. Either by checking the scrapedTime attribute or if the json files already exist or any other mechanism.
- [x] #hig #cor #ftr #7 Fetch: Check for #6 and only spun up browser session if the item is not complete or not already fetched. Else, don't involve the browser. Why: Because spun up the browser, fetch an item's metadata takes time.
- [x] #hig #cor #ftr #8 Fetch: Regarding #6, #7, spun up/use the browser session for fetching an existing/completed item only if the `--force` flag is provided.
- [x] #cri #core #ftr #9 Core: DB layer, a consistent and persistent database layer for storing and retrieving course data, acts as a Single Source of Truth for the whole app.
- [ ] #med #cor #ftr #10 Course: Many courses come with a single resource .pdf file at the very end of the course. This files has been downloaded, but all the links within the pdf are not downloaded yet. These links should be downloaded and save to the same material folder as the pdf (which is the course folder under materials/courses/<course_id>).
- [x] #hig #cor #ftr #11 Fetch: Allow to specify `-s`/`--signin` to sign in with a Google account before fetching: (https://www.skills.google/users/sign_in). Ask user to press Continue (GUI) or Enter (CLI) to proceed after they log in.
- [x] #hig #cor #ftr #12 Fetch: Rename `--no-transcript` to `--md-no-transcript` indicating that the transcript should not be generated into markdown file. However, transcript will be fetched every time the course is fetched, just saving to .json data file only, and ready to be rendered into markdown file later with the `md` command.
- [x] #hig #gui #ftr #13 GUI: Rename the 'Sign in' button to 'Browser' — it opens a browser the user can log in and browse in, and that stays open; subsequent fetch/sync tasks reuse that same browser (via a `browser` command that advertises a Chrome remote-debugging endpoint, which fetches connect to) so the site never re-challenges for sign-in. If reuse is impossible (endpoint unresponsive), the GUI asks the user to acknowledge closing it.
- [x] #hig #cor #ftr #14 Python: cascade backlog #13 to the Python app — a persistent, reusable browser via Selenium `debuggerAddress`, sharing the `browser` command + endpoint-file contract with the Go core.
- [ ] #med #cor #ftr #15 Python: cascade backlog #5 PDF generation — a `pdf` command (single + batch cascade, `--theme`, completeness warning) rendering via `pandoc --pdf-engine=typst`, sharing the `theme/<name>/` manifest + template contract with the Go core.
- [ ] #med #cor #ftr #16 Extra: Generate command or download materials for course with link to html file, for example the course id 1743 (Deploy the Gemini Enterprise app to Transform Enterprises) comes with link likes this "https://storage.googleapis.com/cloud-training/cls-html5-courses/P-DLGITD-I/content/index.html", so the user can download the course materials via the `gcloud storage cp -r` command. (Ex: the current folder means to storage these html files: `gcloud storage cp --recursive 'gs://cloud-training/cls-html5-courses/*' .`)
- [ ] #hig #cor #ftr #17 Core: Items management, able to manage the items saved in the database, sometime wrong items are saved due to manually keying in the item details (id, etc.). For example: at the moment, both path 60 and 264 are not actually existing paths, but recorded in the database without details. For this, the CLI versions should allow a new command such as `db` or `mgmt` which allow to review/delete/alter the items in the database; meanwhile, the GUI version should have a dedicated tab for this, or can allow to right-click and offer a context menu with options to delete/alter the item.

---

THE FOLLOWING PART ARE OUTDATED, A LEGACY PART THAT SHOULD BE UPDATED

---

## TODOs and Future Improvements

1. **Check if published_date is newer, then update the path data**

   - Ensure that the path data is updated if the published date is newer.

2. **Separate webdriver in tasks_coordinator()**

   - Refactor the `tasks_coordinator` function to use separate webdrivers for different tasks.

3. **Check for existing course/lab md files**

   - Implement a check to see if the course/lab markdown files already exists before creating new ones.

4. **Make the collected data persistent**

   - Ensure that the application is stateful and can persist collected data.

5. **Mark correct quiz(es) answers/options**

   - Implement functionality to mark the correct quiz answers/options.

6. **Enable async to speed up the tasks**

   - Use asynchronous programming to speed up the execution of tasks.

7. **Use LLM for transcript formatting**

   - Use a language model to format transcripts and split them into multiple semantic paragraphs.

8. **Support non-login user**

   - Implement functionality to support non-login users.

9. **Remove `<p> <p> <br/>` from the transcript/text/description**

   - Clean up the transcript/text/description by removing unnecessary HTML tags.

## Enhancements & Fixes

### TODO: Extract quiz in lab (`ql-true-false-probe` and `ql-multiple-choice-probe`)

- Example: https://www.cloudskillsboost.google/focuses/1763?parent=catalog

```html
<ql-multiple-choice-probe answerindex="2" optiontitles="[
"Cloud Storage",
"Pub/Sub",
"HTTPS",
"Firebase"
]" shuffle stem="Which type of trigger is used while creating Cloud Run functions in the lab?">
```

```html
<ql-true-false-probe answer="true" stem="Cloud Run functions is a serverless execution environment for event driven services on Google Cloud." >
```

### TODO: Convert document HTML pages or Lab page to Markdown

- Lib: [markdownify](https://github.com/matthewwithanm/python-markdownify)

Example:

- Course: https://www.cloudskillsboost.google/course_templates/1191
- Lab: https://www.cloudskillsboost.google/focuses/1763?parent=catalog
