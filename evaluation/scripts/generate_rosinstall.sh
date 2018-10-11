#!/bin/bash
#
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

echo "- git: {local-name: cartographer, uri: 'https://github.com/${CARTOGRAPHER_FORK}/cartographer.git', version: '${CARTOGRAPHER_BRANCH}'}" > $HOME/cartographer_ros.rosinstall &&
echo "- git: {local-name: cartographer_ros, uri: 'https://github.com/${CARTOGRAPHER_ROS_FORK}/cartographer_ros.git', version: '${CARTOGRAPHER_ROS_BRANCH}'}" >> $HOME/cartographer_ros.rosinstall &&
echo "- git: {local-name: cartographer_fetch, uri: 'https://github.com/googlecartographer/cartographer_fetch.git', version: 'master'}" >> $HOME/cartographer_ros.rosinstall &&
echo "- git: {local-name: ceres-solver, uri: 'https://ceres-solver.googlesource.com/ceres-solver.git', version: '1.13.0'}" >> $HOME/cartographer_ros.rosinstall
