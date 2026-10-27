#!/usr/bin/env bash
set -euo pipefail
# Run only AFTER downloading results. gcloud asks before deleting VMs/disks.
gcloud compute instances delete master worker-1 worker-2 worker-3 worker-4 \
  --zone="${ZONE:-europe-north1-b}" --delete-disks=boot
gcloud compute firewall-rules delete parcs-lab-internal parcs-lab-ssh
gcloud compute networks subnets delete parcs-lab --region="${REGION:-europe-north1}"
gcloud compute networks delete parcs-lab
