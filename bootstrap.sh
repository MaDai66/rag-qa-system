#!/bin/bash

# Start both of langchat's backend and web UI server.
# If the user presses Ctrl+C, kill them both.

export UV_LINK_MODE=copy

if [ "$1" = "--dev" -o "$1" = "-d" -o "$1" = "dev" -o "$1" = "development" ]; then
  echo -e "Starting langchat in [DEVELOPMENT] mode...\n"
  uv run server.py --reload & SERVER_PID=$$!
  trap "kill $$SERVER_PID $$WEB_PID" SIGINT SIGTERM
  wait
else
  echo -e "Starting langchat in [PRODUCTION] mode...\n"
  uv run server.py & SERVER_PID=$$!
  trap "kill $$SERVER_PID $$WEB_PID" SIGINT SIGTERM
  wait
fi
