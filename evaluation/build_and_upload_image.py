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
""" Python tool for building and uploading evaluation docker images.

This tool should be used for building and uploading images that are meant for
running the evaluation pipeline.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from absl import app
from absl import logging
from absl import flags

import docker

FLAGS = flags.FLAGS

flags.DEFINE_string("cartographer_fork", "googlecartographer",
                    "cartographer github fork to use.")
flags.DEFINE_string("cartographer_branch", "master",
                    "cartographer branch (in fork) to use.")
flags.DEFINE_string("cartographer_ros_fork", "googlecartographer",
                    "cartographer_ros github fork to use.")
flags.DEFINE_string("cartographer_ros_branch", "master",
                    "cartographer_ros branch (in fork) to use.")
flags.DEFINE_string("docker_registry", "eu.gcr.io/cartographer-141408",
                    "Url of docker registry to pull the docker image from.")
flags.DEFINE_string("tag", None, "Tag for the docker image.")
flags.DEFINE_string("dockerfile_path", None,
                    "Path to directory containing the Dockerfile.")
flags.DEFINE_bool("verbose", False, "Verbose log output.")


def main(argv):
  if len(argv) > 1:
    raise app.UsageError("Too many command-line arguments.")

  client = docker.from_env()

  build_args = {
      "cartographer_fork": FLAGS.cartographer_fork,
      "cartographer_ros_fork": FLAGS.cartographer_ros_fork,
      "cartographer_branch": FLAGS.cartographer_branch,
      "cartographer_ros_branch": FLAGS.cartographer_ros_branch,
  }

  logging.info("Building image ...")
  full_tag = "{}/{}".format(FLAGS.docker_registry, FLAGS.tag)
  image, build_logs = client.images.build(
      path=FLAGS.dockerfile_path, buildargs=build_args, tag=full_tag)
  if FLAGS.verbose:
    for l in build_logs:
      logging.info("%s", l)

  logging.info("Image built successfully - id: %s tags: %s", image.short_id,
               image.tags)

  logging.info("Pushing image to registry: %s", full_tag)
  for line in client.images.push(full_tag, stream=True):
    if FLAGS.verbose:
      logging.info(line)


if __name__ == "__main__":
  flags.mark_flags_as_required(["tag", "dockerfile_path"])
  app.run(main)
