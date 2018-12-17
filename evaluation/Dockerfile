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

FROM eu.gcr.io/cartographer-141408/evaluation_base:latest

ARG cartographer_fork=googlecartographer
ARG cartographer_branch=master
ARG cartographer_ros_fork=googlecartographer
ARG cartographer_ros_branch=master

ENV CARTOGRAPHER_FORK $cartographer_fork
ENV CARTOGRAPHER_BRANCH $cartographer_branch
ENV CARTOGRAPHER_ROS_FORK $cartographer_ros_fork
ENV CARTOGRAPHER_ROS_BRANCH $cartographer_ros_branch

# Cartographer layer
# First, we invalidate the entire cache if googlecartographer/cartographer has
# changed. This file's content changes whenever master changes. See:
# http://stackoverflow.com/questions/36996046/how-to-prevent-dockerfile-caching-git-clone
ADD https://api.github.com/repos/$cartographer_fork/cartographer/git/refs/heads/$cartographer_branch \
    cartographer_version.json
ADD https://api.github.com/repos/$cartographer_ros_fork/cartographer_ros/git/refs/heads/$cartographer_ros_branch \
    cartographer_ros_version.json

# Generate cartographer_ros.rosinstall:
COPY scripts/generate_rosinstall.sh $HOME/scripts/
RUN $HOME/scripts/generate_rosinstall.sh

COPY scripts/prepare_catkin_workspace.sh $HOME/scripts/
RUN $HOME/scripts/prepare_catkin_workspace.sh
RUN rm -rf $HOME/scripts

ENV CARTO_WORKSPACE $HOME/catkin_ws/src

# Install dependencies.
RUN $CARTO_WORKSPACE/cartographer_ros/scripts/install_debs.sh && rm -rf /var/lib/apt/lists/*

# Build and install.
RUN $CARTO_WORKSPACE/cartographer_ros/scripts/install.sh --pkg cartographer_ros_msgs && \
    $CARTO_WORKSPACE/cartographer_ros/scripts/install.sh --pkg cartographer && \
    $CARTO_WORKSPACE/cartographer_ros/scripts/install.sh --pkg cartographer_ros && \
    $CARTO_WORKSPACE/cartographer_ros/scripts/install.sh --pkg cartographer_fetch && \
    $CARTO_WORKSPACE/cartographer_ros/scripts/install.sh --pkg cartographer_mir && \
    $CARTO_WORKSPACE/cartographer_ros/scripts/install.sh --pkg cartographer_rviz

# Copy the ros_entrypoint.sh
RUN cp ${CARTO_WORKSPACE}/cartographer_ros/scripts/ros_entrypoint.sh /
RUN rm -rf $HOME/catkin_ws

# Copy evaluation pipeline python code.
COPY evaluation_pipeline/__init__.py $HOME/evaluation_pipeline/__init__.py
COPY evaluation_pipeline/cloud_storage_helper.py $HOME/evaluation_pipeline/cloud_storage_helper.py
COPY evaluation_pipeline/big_query_helper.py $HOME/evaluation_pipeline/big_query_helper.py
COPY evaluation_pipeline/pipeline_steps.py $HOME/evaluation_pipeline/pipeline_steps.py
COPY evaluation_pipeline/run_evaluation.py $HOME/evaluation_pipeline/run_evaluation.py

# Reclaim ownership.
RUN chown -R evaluation:evaluation .

# Create scratch dir & redirect ROS logging.
RUN mkdir -p /data/ros_logs
ENV ROS_LOG_DIR /data/ros_logs

# TODO(klose): try running under evaluation user?
#USER evaluation
ENTRYPOINT /ros_entrypoint.sh \
           python evaluation_pipeline/run_evaluation.py
