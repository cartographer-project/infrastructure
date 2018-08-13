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
"""Python tool for creating evaluation jobs from a dataset list.

This tool serves as entry point for kicking off new evaluation jobs. It uses the
python kubernetes client for accessing the cluster and creating batch jobs,
according to the passed command line flags.
"""

from __future__ import absolute_import
from __future__ import print_function

from absl import app
from absl import logging
from absl import flags

from kubernetes import client, config, watch

import k8s_helper
import uuid
import time
import datetime
import csv

FLAGS = flags.FLAGS
flags.DEFINE_string(
    "dataset_list", None,
    "CSV file containing list of datasets with configuration to process.")
flags.DEFINE_string("docker_registry", "eu.gcr.io/robco-klose",
                    "Url of docker registry to pull the docker image from.")
flags.DEFINE_string(
    "docker_image", None,
    "Name or id of the docker image which shall be used as container image for these jobs."
)
flags.DEFINE_list(
    "experiment_id", None,
    "Identifier for this group of evaluations. If not set, a uuid will be generated."
)
flags.DEFINE_list("tags", None, "Tags to add to this experiment")
flags.DEFINE_bool(
    "running_in_cluster", False,
    "Set to true, if this script is executed within a kubernetes cluster")

flags.DEFINE_string(
    "service_secret", None,
    "Path to service account secret. If set, this will be used to auth with GCLOUD."
)


class EvaluationJob(object):
  """All information required to create a single evaluation job."""

  def __init__(self, docker_img, experiment_id, tags, bag_file,
               offline_launch_file, assets_launch_file, ground_truth_file):
    self.docker_image = docker_img
    self.experiment_id = experiment_id
    self.tags = tags
    self.bag_file = bag_file
    self.offline_launch_file = offline_launch_file
    self.assets_launch_file = assets_launch_file
    self.ground_truth_file = ground_truth_file
    self.uuid = str(uuid.uuid1())


class KubernetesJobCreator(object):
  """Helper object for creating kubernetes jobs."""

  def __init__(self, running_in_cluster, namespace="default"):
    self.config = k8s_helper.create_config(running_in_cluster)
    # Service account secret, this has to be already created in the cluster.
    self.secret_name = "evaluation-secret"
    self.namespace = namespace
    self.k8s_core_api = client.CoreV1Api()
    self.k8s_batch_api = k8s_helper.create_batch_api(self.config)
    self.creation_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # Specific for job creation.
    self.job_args = ["python", "evaluation_pipeline/run_evaluation.py"]

  def createJob(self, evaluation_job):
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=evaluation_job.uuid),
        spec=client.V1JobSpec(
            template=self._create_pod_template_spec_for_job(evaluation_job),
            backoff_limit=0,
            completions=1,
            parallelism=1))

    logging.info("Creating evaluation job on kubernetes.")
    self.try_create_job(job)

  def try_create_job(self, k8s_job):
    try:
      response = self.k8s_batch_api.create_namespaced_job(
          self.namespace, k8s_job, pretty="true")
    except client.rest.ApiException as e:
      logging.error(
          "Error when calling BatchV1Api.create_namespaced_job(...): %s", e)

  def _create_pod_template_spec_for_job(self, evaluation_job):
    return client.V1PodTemplateSpec(
        spec=client.V1PodSpec(
            containers=[self._create_container(evaluation_job)],
            volumes=[self._create_secret_volume()],
            restart_policy="Never"))

  def _create_secret_volume(self):
    return client.V1Volume(
        name=self.secret_name,
        secret=client.V1SecretVolumeSource(
            secret_name=self.secret_name, optional=False))

  def _create_container(self, evaluation_job):
    return client.V1Container(
        name=evaluation_job.uuid,
        image=evaluation_job.docker_image,
        command=["/ros_entrypoint.sh"],
        args=self._create_job_args(evaluation_job),
        volume_mounts=[
            client.V1VolumeMount(
                name=self.secret_name, mount_path="/var/secrets/evaluation")
        ],
        env=[
            client.V1EnvVar(
                name="GOOGLE_APPLICATION_CREDENTIALS",
                value="/var/secrets/evaluation/key.json")
        ],
        resources=self._create_resource_requirements())

  def _create_job_args(self, evaluation_job):
    eval_arguments = [
        "--dataset_path", evaluation_job.bag_file, "--launch_file",
        evaluation_job.offline_launch_file, "--assets_launch_file",
        evaluation_job.assets_launch_file, "--uuid", evaluation_job.uuid,
        "--experiment_id", evaluation_job.experiment_id, "--creation_date",
        self.creation_date
    ]

    # Optional arguments.
    if evaluation_job.tags:
      eval_arguments.append("--tags")
      eval_arguments.append(",".join(evaluation_job.tags))
    if evaluation_job.ground_truth_file:
      eval_arguments.append("--ground_truth_relations")
      eval_arguments.append(evaluation_job.ground_truth_file)

    return self.job_args + eval_arguments

  def _create_resource_requirements(self):
    # TODO(klose): Make these optional columns in the csv.
    limits = {"memory": "30Gi", "cpu": "8"}
    requests = {"memory": "12Gi", "cpu": "4"}
    return client.V1ResourceRequirements(limits=limits, requests=requests)


def csv_to_evaluation_jobs(csv_filename, docker_img, experiment_id, tags):
  """Loads csv file with list of evaluation jobs and returns [EvaluationJob].

   The first row of the CSV file is assumed to specify the column names as
  follows:
   dataset, offline_launch_file, assets_writer_launch_file, ground_truth_file
  """

  eval_jobs = []
  with open(csv_filename, "rb") as f:
    reader = csv.DictReader(filter(lambda row: row[0] != "#", f))
    eval_jobs = [
        EvaluationJob(docker_img, experiment_id, tags, row["dataset"].strip(),
                      row["offline_launch_file"].strip(),
                      row["assets_writer_launch_file"].strip(),
                      row["ground_truth_file"].strip()) for row in reader
    ]
  return eval_jobs


def main(argv):
  if len(argv) > 1:
    raise app.UsageError("Too many command-line arguments.")

  experiment_id = FLAGS.experiment_id
  if not experiment_id:
    experiment_id = str(uuid.uuid1())

  docker_image = "{}/{}".format(FLAGS.docker_registry, FLAGS.docker_image)
  evaluation_jobs = csv_to_evaluation_jobs(FLAGS.dataset_list, docker_image,
                                           experiment_id, FLAGS.tags)

  creator = KubernetesJobCreator(FLAGS.running_in_cluster)
  v1_api = creator.k8s_core_api
  jobs_to_monitor = {}
  for job in evaluation_jobs:
    logging.info("Creating evaluation job: %s", job.uuid)
    creator.createJob(job)
    jobs_to_monitor[job.uuid] = job

  # Create a watch on all pods of the cluster and find the ones matching the
  # newly created jobs.
  w = watch.Watch()
  num_succeeded = 0
  num_failed = 0
  waiting_for_finish = len(jobs_to_monitor)
  for e in w.stream(v1_api.list_namespaced_pod, "default"):
    pod = e["object"]
    event_type = e["type"]
    if pod.spec.containers:
      for c in pod.spec.containers:
        if c.name in jobs_to_monitor:
          logging.info("Job %s signalled event %s, POD Phase: %s", c.name,
                       event_type, pod.status.phase)
          if pod.status.phase == "Succeeded":
            num_succeeded += 1
            waiting_for_finish -= 1
          elif pod.status.phase == "Failed":
            num_failed += 1
            waiting_for_finish -= 1
          logging.info("Waiting for %d jobs to finish", waiting_for_finish)
    if waiting_for_finish <= 0:
      break


if __name__ == "__main__":
  flags.mark_flags_as_required(["dataset_list", "docker_image"])
  app.run(main)
