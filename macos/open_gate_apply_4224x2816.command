#!/bin/bash
# A7S III (firmware 5.01): apply the 4224x2816 state (NOT RUN ON A CAMERA YET): the central 4224x2816 of the sensor pixel for pixel, the screen at 3:2 and the C3 preview cycle.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply apply4224 "$@"
