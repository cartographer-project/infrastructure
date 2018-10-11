#!/bin/bash
set -o errexit
set -o verbose

sh update_nightly_docker.sh

kubectl delete cronjobs nightly-evaluation
kubectl create -f k8s_nightly_cronjob.yaml
