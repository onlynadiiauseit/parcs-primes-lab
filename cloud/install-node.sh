#!/usr/bin/env bash
set -euo pipefail
node="$1"
ip="$2"
cd "$(dirname "$0")/.."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y docker.io
systemctl enable --now docker
docker build -t parcs-primes:lab .
args=(-ip "$ip" -port 8080)
if [[ "$node" != master ]]; then
  args+=(-master_ip 10.42.0.10 -master_port 8080)
fi
docker run -d --name parcs --restart=unless-stopped --network=host \
  --hostname="$node" parcs-primes:lab "${args[@]}"
