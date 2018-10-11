# Copyright 2018 The Cartographer Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Helpers for working with the kubernetes client api

Collection of helper functions and classes for easing the use of the kubernetes
python client API.
"""

from __future__ import absolute_import

import pytz
from absl import logging
from datetime import datetime, timedelta
from kubernetes import client, config, watch


def create_config(in_cluster=False):
  if in_cluster:
    logging.info("Loading in-cluster config")
    return config.load_incluster_config()
  else:
    return config.load_kube_config()


def create_batch_api(cfg):
  return client.BatchV1Api(client.ApiClient(cfg))


def list_jobs(batch_api, namespace="default"):
  try:
    jobs = batch_api.list_namespaced_job(namespace, pretty="true")
    return jobs
  except client.rest.ApiException as e:
    logging.error("Cannot list jobs: %s", e)
    return None


def delete_failed_jobs(batch_api, namespace="default"):
  all_jobs = list_jobs(batch_api, namespace)
  for j in all_jobs.items:
    logging.info("Checking job %s, active: %s", j.metadata.name,
                 str(j.status.active))
    if j.status.active == None:
      failed = j.status.failed
      if failed != None and failed > 0:
        try:
          logging.info("Deleting job %s", j.metadata.name)
          batch_api.delete_namespaced_job(
              j.metadata.name, namespace,
              client.V1DeleteOptions(propagation_policy="Foreground"))
        except client.rest.ApiException as e:
          logging.error("Cannot delete job: %s", j.metadata.name)


def garbage_collect_jobs(batch_api, namespace, min_age_in_days):
  """ Deletes all completed kubernetes jobs above a certain age.

  Will check all existing k8s jobs in `namespace` and delete them if their age
  in days is greater or equal to `min_age_in_days`.
  """
  all_jobs = list_jobs(batch_api, namespace)
  now = datetime.now(pytz.utc)
  for job in all_jobs.items:
    status = job.status
    if status.completion_time:
      delta_t = now - status.completion_time
      if delta_t.days >= min_age_in_days:
        try:
          logging.info("Deleting job %s, completed %d days ago.",
                       job.metadata.name, delta_t.days)
          batch_api.delete_namespaced_job(
              job.metadata.name, namespace,
              client.V1DeleteOptions(propagation_policy="Foreground"))
        except client.rest.ApiException as e:
          logging.error("Cannot delete job: %s", job.metadata.name)


def monitor_jobs(v1_api, jobs_to_monitor, namespace="default"):
  """Creates a watch to monitor all jobs in `jobs_to_monitor`.

  The function will "block" until all jobs are completed. And report back the
  number of succeeded and failed pods.
  """
  w = watch.Watch()
  num_succeeded = 0
  num_failed = 0
  for e in w.stream(v1_api.list_namespaced_pod, namespace):
    pod = e["object"]
    event_type = e["type"]
    if pod.spec.containers:
      for c in pod.spec.containers:
        if c.name in jobs_to_monitor:
          logging.info("Job %s signalled event %s, POD Phase: %s", c.name,
                       event_type, pod.status.phase)
          if pod.status.phase == "Succeeded":
            num_succeeded += 1
            jobs_to_monitor.pop(c.name)
          elif pod.status.phase == "Failed":
            num_failed += 1
            jobs_to_monitor.pop(c.name)
          logging.info("Waiting for %d jobs to finish", len(jobs_to_monitor))
    if len(jobs_to_monitor) <= 0:
      break
  return num_succeeded, num_failed
