# CONTRIBUTION

Every contribution is very much welcomed!

## Backglog

- [ ] MD to PDF conversion with styles using [Typst](https://typst.app).
- [ ] The GUI is freezing when some browser-activity is performed. Decouple browser-activity from the GUI thread.
- [ ] Handle `https://www.skills.google/users/sign_in` if the user is not already signed in.
- [ ] CLI: Allow to login/open the browser, and then re-use the browser session for subsequent requests (fetching).
- [ ] Shut down the browser session gracefully, even when the application is terminated.

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
