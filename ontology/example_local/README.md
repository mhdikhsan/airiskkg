# Local example graphs

Put your own architecture graphs here. Anything in this folder is **yours and
stays here**: confidential systems, NDA-covered use cases, work in progress.

This is the only file in the folder that git tracks. Every `.ttl` you add is
ignored, so `git add .` cannot pull it in, and the Docker build excludes the
folder outright — a graph you drop here cannot reach the repository or a
deployed image by forgetting something.

## Using them

Run the workbench locally and your graphs appear in **Load example**, under a
*Local* heading so you can always tell them apart from the two the project
ships:

```
python -m airiskkg.cli serve
```

Or assess one straight from the command line:

```
python -m airiskkg.cli assess ontology/example_local/my_system.ttl
```

A deployed server (gunicorn, Docker, anything that is not `cli serve`) never
lists this folder, even if the files somehow reach its disk. Turn it off for a
local run too with `PAIR_AI_LOCAL_EXAMPLES=0`.

## What the project ships

`ontology/example/` holds the public examples — a RAG chatbot and a minimal
graph RAG — so someone trying the tool has something to load. The test suite
uses only those, and never reads this folder: a fresh clone has to pass.
