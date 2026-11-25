#!/bin/bash
# A7S III (firmware 5.01): apply 3840x2560 open gate without the MP4 header height (N19, headers stay 3840x2160), plus the screen at 3:2 and C3 preview cycle.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply apply --no-meta "$@"
