## TODO

- [x] Create the `data` folder if it does not exist to avoid the below `FileNotFoundError` error.

```bash
$ uv run app/main.py list

Launching browser for list extraction...
Reloading paths list from remote...
Closing browser...
Traceback (most recent call last):
  File "/Users/samdinh/repos/csbhelper/app/main.py", line 379, in <module>
    main()
  File "/Users/samdinh/repos/csbhelper/app/main.py", line 376, in main
    args.func(args)
  File "/Users/samdinh/repos/csbhelper/app/main.py", line 41, in cmd_list
    collection.load_json()
  File "/Users/samdinh/repos/csbhelper/app/models/collection.py", line 72, in load_json
    db = Database()
         ^^^^^^^^^^
  File "/Users/samdinh/repos/csbhelper/app/services/database.py", line 12, in __new__
    cls._instance._initialize()
  File "/Users/samdinh/repos/csbhelper/app/services/database.py", line 19, in _initialize
    self.db = TinyDB(self.db_path, indent=2, encoding='utf-8')
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/samdinh/repos/csbhelper/.venv/lib/python3.12/site-packages/tinydb/database.py", line 94, in __init__
    self._storage: Storage = storage(*args, **kwargs)
                             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/samdinh/repos/csbhelper/.venv/lib/python3.12/site-packages/tinydb/storages.py", line 113, in __init__
    touch(path, create_dirs=create_dirs)
  File "/Users/samdinh/repos/csbhelper/.venv/lib/python3.12/site-packages/tinydb/storages.py", line 32, in touch
    with open(path, 'a'):
         ^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: '/Users/samdinh/repos/csbhelper/data/database.json'
```

- [] Migrate to `uv` package management tool.
- Command-line interface.
- Do not over-write the existing Markdown files, it's actually up to you, as a user.
- Call to Gemini/LLAMA or any other LLM for helping summarize/re-formatting the transcripts.
   + For time being, Gemini for me, is not so good so I don't use yet.
   + LM Studio is a good choice with LLAMA 3.1, 3.2 but my machine is not suitable for running this continously.
- An implementation for [https://partner.cloudskillsboost.google/](https://partner.cloudskillsboost.google/)

Check [CONTRIBUTION](CONTRIBUTION.md) for more.

- [ ] TODO: Sync the data folder to a GCS bucket: `gcloud storage rsync --recursive data/ gs://csbhelper/`
