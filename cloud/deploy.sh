#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-europe-north1}"
ZONE="${ZONE:-europe-north1-b}"
if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == '(unset)' ]]; then
  echo 'First run: gcloud config set project YOUR_PROJECT_ID' >&2
  exit 1
fi
export CLOUDSDK_CORE_PROJECT="$PROJECT_ID"
nodes=(master worker-1 worker-2 worker-3 worker-4)
for node in "${nodes[@]}"; do
  if gcloud compute instances describe "$node" --zone="$ZONE" >/dev/null 2>&1; then
    echo "Instance $node already exists. Do not rerun deployment over existing nodes." >&2
    exit 1
  fi
done
gcloud services enable compute.googleapis.com iap.googleapis.com
if ! gcloud compute networks describe parcs-lab >/dev/null 2>&1; then
  gcloud compute networks create parcs-lab --subnet-mode=custom
fi
if ! gcloud compute networks subnets describe parcs-lab --region="$REGION" >/dev/null 2>&1; then
  gcloud compute networks subnets create parcs-lab --network=parcs-lab \
    --region="$REGION" --range=10.42.0.0/24
fi
if ! gcloud compute firewall-rules describe parcs-lab-internal >/dev/null 2>&1; then
  gcloud compute firewall-rules create parcs-lab-internal --network=parcs-lab \
    --allow=tcp:8080,tcp:9090 --source-tags=parcs-lab --target-tags=parcs-lab
fi
if ! gcloud compute firewall-rules describe parcs-lab-ssh >/dev/null 2>&1; then
  gcloud compute firewall-rules create parcs-lab-ssh --network=parcs-lab \
    --allow=tcp:22 --source-ranges=35.235.240.0/20 --target-tags=parcs-lab
fi
# Each machine receives an ephemeral external IP for outbound package downloads.
# PARCS ports are accessible only between these machines, never from the Internet.
for index in "${!nodes[@]}"; do
  node="${nodes[$index]}"
  gcloud compute instances create "$node" --zone="$ZONE" \
    --machine-type=e2-standard-2 --network=parcs-lab --subnet=parcs-lab \
    --private-network-ip="10.42.0.$((10+index))" --tags=parcs-lab \
    --image-family=debian-12 --image-project=debian-cloud \
    --boot-disk-size=10GB --boot-disk-type=pd-standard \
    --no-service-account --no-scopes --labels=lab=parcs-primes
 done
tar --exclude=.git --exclude=results --exclude=__pycache__ --exclude=.venv \
  -czf /tmp/parcs-lab-upload.tar.gz .
for index in "${!nodes[@]}"; do
  node="${nodes[$index]}"
  ready=false
  for attempt in $(seq 1 24); do
    if gcloud compute ssh "$node" --zone="$ZONE" --tunnel-through-iap --quiet \
       --command=true; then ready=true; break; fi
    sleep 5
  done
  if [[ "$ready" != true ]]; then
    echo "SSH not ready for $node. Check IAP permissions and VM status." >&2
    exit 1
  fi
  gcloud compute scp /tmp/parcs-lab-upload.tar.gz "$node:~/parcs-lab-upload.tar.gz" \
    --zone="$ZONE" --tunnel-through-iap --quiet
  gcloud compute ssh "$node" --zone="$ZONE" --tunnel-through-iap --quiet \
    --command="mkdir -p ~/parcs-lab && tar -xzf ~/parcs-lab-upload.tar.gz -C ~/parcs-lab && sudo bash ~/parcs-lab/cloud/install-node.sh '$node' '10.42.0.$((10+index))'"
done
mkdir -p results
gcloud compute instances list --filter='labels.lab=parcs-primes' \
  --format='table(name,zone.basename(),machineType.basename(),networkInterfaces[0].networkIP,status)' | tee results/nodes.txt
echo 'Deployment complete. Next: bash cloud/tunnel.sh'
