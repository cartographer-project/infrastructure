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

from absl import logging
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
              j.metadata.name,
              namespace,
              client.V1DeleteOptions(propagation_policy="Foreground"))
        except client.rest.ApiException as e:
          logging.error("Cannot delete job: %s", j.metadata.name)
