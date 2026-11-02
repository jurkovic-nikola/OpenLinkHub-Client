#!/bin/sh
export PYTHONPATH=/app/share/olh-client${PYTHONPATH:+:$PYTHONPATH}
exec python3 -m olhclient "$@"
