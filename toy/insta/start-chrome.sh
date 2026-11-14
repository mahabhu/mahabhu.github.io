#!/usr/bin/env bash
# Start a separate Chrome profile with remote control on port 9222.
# Chrome refuses remote debugging on your default profile, so this uses its own folder.
# Log in to Instagram once in this window; the login is kept for next time.
PROFILE="${PROFILE:-$HOME/.chrome-insta}"
exec google-chrome --remote-debugging-port=9222 --user-data-dir="$PROFILE" \
  --no-first-run "https://accountscenter.instagram.com/?entry_point=app_settings" "$@"
