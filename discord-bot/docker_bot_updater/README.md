# Docker Bot Updater

This is a separate docker that is response for watching the github repo, and when it changes, automatically rebuilds and pushes the docker image to the local docker registry.

If the main docker image is ever pushed to dockerhub, this is 1000000% useless.

* build-and-push.sh: builds the updater image and pushes it to the local registry
* docker-compose.yaml: Sample docker compose. It assumes your networking is properly setup
* main.py: The main script that watches the repo and triggers builds, also includes some functions for checking connection
* requirements.txt: Python dependencies for the updater

Is this all an attempt to *not* use dockerhub and github runners to build the docker? Yes.
