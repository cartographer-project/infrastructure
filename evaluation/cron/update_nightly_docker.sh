#!/bin/bash
set -o errexit
set -o verbose
docker_registry=eu.gcr.io/cartographer-141408
docker build -t ${docker_registry}/nightly_cron -f nightly_cron.Dockerfile ..
docker push ${docker_registry}/nightly_cron
