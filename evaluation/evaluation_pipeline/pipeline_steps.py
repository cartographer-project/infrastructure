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
"""Function definitions for the single evaluation pipeline steps.

Each function below, can be seen as one step of the evaluation pipeline.
"""
from __future__ import absolute_import
from absl import logging
from shutil import copyfile

import os
import roslaunch
import rospkg
import subprocess


class ProcessListener(roslaunch.pmon.ProcessListener):

  def __init__(self):
    self.success = True
    self.name = ''
    self.exit_code = 0

  def process_died(self, name, exit_code):
    self.success = False
    self.name = name
    self.exit_code = exit_code
    logging.info('%s died with code %s', name, exit_code)


def roslaunch_helper(package_name, launch_file, arguments, run_id=None):
  uuid = roslaunch.rlutil.get_or_generate_uuid(run_id, False)
  roslaunch.configure_logging(uuid)

  roslaunch_cli = [package_name, launch_file]
  roslaunch_file = roslaunch.rlutil.resolve_launch_arguments(roslaunch_cli)[0]
  roslaunch_files = [(roslaunch_file, arguments)]

  process_listener = ProcessListener()
  launch = roslaunch.parent.ROSLaunchParent(
      uuid, roslaunch_files, process_listeners=[process_listener])
  launch.start()
  logging.info('Waiting for launched process to terminate ...')
  launch.spin()
  return process_listener.success


def run_cmd(cmd):
  """Runs command both printing its stdout output and returning it as string."""
  print cmd
  p = subprocess.Popen(
      cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  run_cmd.output = []

  def process(line):
    run_cmd.output.append(line)
    logging.info(line.rstrip())

  while p.poll() is None:
    process(p.stdout.readline())
  process(p.stdout.read())
  return '\n'.join(run_cmd.output)


def create_pbstream(launch_file, bagfile):
  logging.info('Generating pbstream for bagfile: %s', bagfile)
  launch_args = ['no_rviz:=true', 'bag_filenames:={}'.format(bagfile)]
  return roslaunch_helper('cartographer_ros', launch_file, launch_args,
                          'offline_node')


def copy_logs(folder_in_ros_log, destination):
  src = '{}/{}/rosout.log'.format(os.environ['ROS_LOG_DIR'], folder_in_ros_log)
  copyfile(src, destination)


# Generate assets for the pose_graph + bag_file, using the "device" specific
# launch file.
def create_assets(launch_file, bagfile, pose_graph_file):
  logging.info('Generating assets for bagfile %s and PoseGraph %s', bagfile,
               pose_graph_file)
  launch_args = [
      'bag_filenames:={}'.format(bagfile),
      'pose_graph_filename:={}'.format(pose_graph_file),
  ]
  return roslaunch_helper('cartographer_ros', launch_file, launch_args,
                          'assets_writer')


def calculate_groundtruth_metrics(ground_truth_file, pose_graph_file):
  output = run_cmd('cartographer_compute_relations_metrics '
                   '-write_relation_metrics '
                   '-relations_filename {} '
                   '-pose_graph_filename {}'.format(ground_truth_file,
                                                    pose_graph_file))
  return output
