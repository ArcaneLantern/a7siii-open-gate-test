#!/bin/bash
# A7S III (firmware 5.01): apply the default state: 3840x2560 open gate, the screen at 3:2 and the C3 preview cycle (five steps, then one read-only session).
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the tester's camera the power switch did too.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply apply "$@"
