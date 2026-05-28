#!/bin/bash
# Destroys ALL AWS resources to stop billing. Run when experiments are done.
set -e
cd "$(dirname "$0")/../infra"
echo "WARNING: This will destroy all AWS resources in the TicketServiceStack."
read -p "Type 'yes' to confirm: " confirm
[ "$confirm" = "yes" ] || { echo "Aborted."; exit 1; }
cdk destroy --force
echo "Stack destroyed. No more billing."
