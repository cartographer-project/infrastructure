#!/bin/bash
set -o errexit
set -o verbose

docker build -t eu.gcr.io/robco-klose/nightly_cron -f nightly_cron.Dockerfile ..
docker push eu.gcr.io/robco-klose/nightly_cron

# currently we schedule jobs "nightly" at 20:00 UTC.
kubectl delete cronjobs nightly-evaluation
kubectl create -f k8s_nightly_cronjob.yaml
