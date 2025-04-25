## TODO

- Command-line interface.
- Do not over-write the existing Markdown files, it's actually up to you, as a user.
- Call to Gemini/LLAMA or any other LLM for helping summarize/re-formatting the transcripts.
   + For time being, Gemini for me, is not so good so I don't use yet.
   + LM Studio is a good choice with LLAMA 3.1, 3.2 but my machine is not suitable for running this continously.
- An implementation for [https://partner.cloudskillsboost.google/](https://partner.cloudskillsboost.google/)

Check [CONTRIBUTION](CONTRIBUTION.md) for more.

-[ ] TODO: Sync the data folder to a GCS bucket: `gcloud storage rsync --recursive data/ gs://csbhelper/`
