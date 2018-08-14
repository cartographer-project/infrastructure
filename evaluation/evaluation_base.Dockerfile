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

# This is a base image, which should serve to minimize the cloud build time,
# by ensuring almost all dependnecies are already installed.

FROM ros:melodic

ENV CARTOGRAPHER_FORK googlecartographer
ENV CARTOGRAPHER_BRANCH master
ENV CARTOGRAPHER_ROS_FORK googlecartographer
ENV CARTOGRAPHER_ROS_BRANCH master

# Bionic's base image doesn't ship with sudo.
RUN apt-get update && \
    apt-get install -y sudo ninja-build && \
    apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*

# Define evaluation environment.
ENV HOME /home/evaluation
RUN apt-get update && \
    apt-get -y install curl python-pip time && \
    addgroup --system --gid 10000 evaluation && \
    adduser --system --ingroup evaluation --home $HOME --uid 10000 evaluation
WORKDIR $HOME

# Cloud SDK layer
ENV CLOUDSDK_CORE_DISABLE_PROMPTS 1
ENV PATH /opt/google-cloud-sdk/bin:$PATH

# Install Google Cloud Components
RUN curl https://sdk.cloud.google.com | bash && \
    mv google-cloud-sdk /opt && \
    gcloud components install kubectl && \
    pip install --upgrade absl-py && \
    pip install --upgrade google-cloud-bigquery && \
    pip install --upgrade google-cloud-storage

# Cartographer layer
# First, we invalidate the entire cache if googlecartographer/cartographer has
# changed. This file's content changes whenever master changes. See:
# http://stackoverflow.com/questions/36996046/how-to-prevent-dockerfile-caching-git-clone
ADD https://api.github.com/repos/googlecartographer/cartographer/git/refs/heads/master \
    orig_cartographer_version.json
ADD https://api.github.com/repos/googlecartographer/cartographer_ros/git/refs/heads/master \
    orig_cartographer_ros_version.json

# Generate cartographer_ros.rosinstall.
COPY scripts/generate_rosinstall.sh $HOME/scripts/
RUN $HOME/scripts/generate_rosinstall.sh

COPY scripts/prepare_catkin_workspace.sh $HOME/scripts/
RUN $HOME/scripts/prepare_catkin_workspace.sh
RUN rm -rf $HOME/scripts

ENV CARTO_WORKSPACE $HOME/catkin_ws/src

# Hack to overcome ascii encoding problem when running `rosdep install ...`
# TODO(klose): find a proper solution.
RUN sed -i -e 's/ö/oe/g' /opt/ros/${ROS_DISTRO}/share/roslisp/manifest.xml

# Install dependencies:
RUN $CARTO_WORKSPACE/cartographer_ros/scripts/install_debs.sh && rm -rf /var/lib/apt/lists/*

# Install proto3, cartographer_ros_msgs and ceres-solver.
RUN $CARTO_WORKSPACE/cartographer/scripts/install_proto3.sh && \
    $CARTO_WORKSPACE/cartographer_ros/scripts/install.sh --pkg cartographer_ros_msgs && \
    $CARTO_WORKSPACE/cartographer_ros/scripts/install.sh --pkg ceres-solver && \
    rm -rf $HOME/protobuf && \
    rm -rf $HOME/catkin_ws

# Reclaim ownership.
RUN chown -R evaluation:evaluation .
