#!/bin/bash
# A7S III (firmware 5.01): apply only the three open-gate steps, without the two screen steps.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the tester's camera the power switch did too.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply apply --no-screen "$@"
