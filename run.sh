#!/usr/bin/env bash
set -euo pipefail
# Explicit addresses are required in the cloud; see cloud/install-node.sh.
exec python3 start.py "$@"
