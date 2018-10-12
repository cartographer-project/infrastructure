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
"""Run evaluation for a single dataset and launch configuration.

This app assumes to run in a ROS environment with cartographer_ros installed.
The script will run through the following steps to produce evaluation artifacts
for the specified bag_file - launch_file combination:
  * download the bagfile from the specified location
  * run the launch file to produce a pbstream (usually offline_node)
  * generate artifacts by running the specified assets_launch_file
  * if groud_truth_relations file is specified:
    - download ground_truth_relations
    - compare generated maps against downloaded ground truth
    - store a csv file containing errors / relations
    - store relation error into a bigquery table
  * upload generated artifacts to cloud storage
"""

from __future__ import absolute_import

from absl import app
from absl import flags
from absl import logging
from time import sleep

from cloud_storage_helper import download_from_cloud_storage_url
from cloud_storage_helper import path_to_blob
from cloud_storage_helper import upload_artifacts
from big_query_helper import store_in_bigquery
import pipeline_steps

import os
import subprocess

FLAGS = flags.FLAGS
flags.DEFINE_string(
    'dataset_path', None,
    'Cloud storage path to dataset to process (via gs://... ).')
flags.DEFINE_string('ground_truth_relations', None,
                    'Cloud storage path to ground truth relations file.')
flags.DEFINE_string('output_bucket', 'cartographer-evaluation-artifacts',
                    'Cloud storage bucket for output artifacts.')
flags.DEFINE_string('platform', 'Unknown',
                    'The platform that was used to record this dataset.')
flags.DEFINE_string('launch_file', None,
                    'launch file from `flags.launch_file_pkg` to use.')
flags.DEFINE_string('launch_file_pkg', 'cartographer_ros',
                    'Package in which we assume the launch file.')
flags.DEFINE_string(
    'configuration_file', None,
    """Optional configuration file to use (e.g. for parameter sweeps). Assumed
    to be a cloud storage path.""")
flags.DEFINE_string(
    'assets_launch_file', None,
    'launch file from cartographer_ros to use for assets generation.')
flags.DEFINE_string('secret', '/var/secrets/evaluation/key.json',
                    'Path to cloud access secret.')
# Metainformation to help identifying this job.
flags.DEFINE_string('experiment_id', None,
                    'Identifier for the experiment this job is part of.')
flags.DEFINE_string(
    'uuid', None,
    """Unique identifier for this evaluation run (will be used as result
    artifacts directory.""")
flags.DEFINE_string('creation_date', None,
                    'Date on which this job was created (YYYY-MM-DD)')
flags.DEFINE_list(
    'tags', None,
    'Optional list of tags to be added to the bigquery table entries.')


def main(argv):
  if len(argv) > 1:
    raise app.UsageError('Too many command-line arguments.')
  print('RUNNING EVALUATION FOR:\n'
        '  Dataset:       {}\n'
        '  Launch file:   {}\n'
        '  Assets launch: {}\n'
        '  UUID:          {}'.format(FLAGS.dataset_path, FLAGS.launch_file,
                                     FLAGS.assets_launch_file, FLAGS.uuid))

  bag_file = os.path.basename(FLAGS.dataset_path)
  scratch_dir = '/data/{}'.format(FLAGS.uuid)
  if not os.path.exists(scratch_dir):
    os.makedirs(scratch_dir)

  destination = '{}/{}'.format(scratch_dir, bag_file)

  if not download_from_cloud_storage_url(FLAGS.dataset_path, destination,
                                         FLAGS.secret):
    return

  config_dst = None
  if FLAGS.configuration_file:
    config_dst = '{}/{}'.format(scratch_dir, 'config.lua')
    if not download_from_cloud_storage_url(FLAGS.configuration_file, config_dst,
                                           FLAGS.secret):
      return

  pipeline_steps.create_pbstream(FLAGS.launch_file_pkg, FLAGS.launch_file,
                                 destination, config_dst)
  pipeline_steps.copy_logs('offline_node',
                           '{}/offline_node.log'.format(scratch_dir))
  logging.info('pbstream successfully created!')

  pose_graph_file = '{}.pbstream'.format(destination)
  if FLAGS.assets_launch_file:
    pipeline_steps.create_assets(FLAGS.launch_file_pkg,
                                 FLAGS.assets_launch_file, destination,
                                 pose_graph_file)
    pipeline_steps.copy_logs('assets_writer',
                             '{}/assets_writer.log'.format(scratch_dir))

  if FLAGS.ground_truth_relations:
    logging.info('Getting ground truth relations file: %s',
                 FLAGS.ground_truth_relations)
    relations_file = '{}/ground_truth_relations.pbstream'.format(scratch_dir)
    if not download_from_cloud_storage_url(FLAGS.ground_truth_relations,
                                           relations_file, FLAGS.secret):
      logging.error('Could not download ground truth relations file.')
      return

    pipeline_steps.calculate_groundtruth_metrics(relations_file,
                                                 pose_graph_file)

    logging.info('Storing results to bigquery')
    store_in_bigquery(scratch_dir, FLAGS.experiment_id, FLAGS.uuid, bag_file,
                      FLAGS.platform, FLAGS.secret, FLAGS.creation_date,
                      FLAGS.tags)

  destination_path = '{}/{}'.format(FLAGS.experiment_id, FLAGS.uuid)
  upload_artifacts(scratch_dir, FLAGS.output_bucket, destination_path,
                   FLAGS.secret)


if __name__ == '__main__':
  flags.mark_flags_as_required(
      ['dataset_path', 'launch_file', 'experiment_id', 'uuid', 'creation_date'])
  app.run(main)
