#!/usr/bin/env bash
set -euo pipefail
# Stops CPU billing; disks remain. Start the same VMs to continue later.
gcloud compute instances stop master worker-1 worker-2 worker-3 worker-4 \
  --zone="${ZONE:-europe-north1-b}"
