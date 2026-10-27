#!/usr/bin/env bash
set -euo pipefail
gcloud compute ssh master --zone="${ZONE:-europe-north1-b}" --tunnel-through-iap \
  -- -N -L 8080:127.0.0.1:8080 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30
