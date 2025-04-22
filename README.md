# Google Cloud Skills Boost Automation/Scraping Script

![Welcome Screen](docs/assets/welcome-screen.png)

A helper or a scraper.

## How to run this with Docker

1. Clone the repo.
2. `cd` to the repo's folder.
3. `docker build -t csbhelper .`
4. `docker run -dp '8080:8080' csbhelper`
5. Start to browse the web UI at `localhost:8080`.

## TL;DR

This is a small tools for scraping contents from Google Cloud Skills Boost website to Markdown files, which helps to build your Personal Knowledge Base, Obsidian, for example.

The idea:

1. Extract the courses' content from CSB website into Markdown files.
2. Manage/update those contents in your Personal Knowledge Base (Obsidian for example).

To start:

1. Update `config/settings.py` file to meet your environment.
2. Create a `venv` for your Python distribution, for example `.venv`.
3. Install dependencies from `requirements.txt`: `pip3 install -r requirements.txt`.
4. Start download with the `scrapter.py`.

```bash
python scrapter.py
```

Hint:

- A simple web interface to browse your downloaded courses.

```bash
python app.py
```

5. Open output Markdown files with your Obsidian or any other similar software.

## Features

- Gathers a list of Path.
- Offer selection to specify a course or list of courses.
- Extract the course(s)' content, including id, title, tag, videos' transcript, and quiz.
- Write path's or course's content to a well-structured Markdown file for each.
- Can also help to 'Mark Complete Video' as well.
- Generate prompt for LLM to re-formatting the videos' transcripts.

## Example of Obsidian

File View.

![Obsidian File View](docs/assets/obsidian-files.png)

Graph View.

![Obsidian File View](docs/assets/obsidian-graph.png)

The script in action.

![The script in action](docs/assets/script-in-action.png)

## Further Reading

1. [Installation](docs/installation.md)
2. [Usage](docs/usage.md)
3. [How does the data files look like?](docs/data.md)
4. [How does the Markdown files look like?](docs/output.md)
5. [Generate prompts to formatting transcript?](docs/promt-llm.md)
