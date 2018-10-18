#!/bin/bash
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

set -o errexit
set -o verbose

BASE=eu.gcr.io/cartographer-141408
TAG=${BASE}/eval_nightly

docker build -t ${TAG} -f Dockerfile \
  --build-arg cartographer_fork=googlecartographer \
  --build-arg cartographer_branch=master \
  --build-arg cartographer_ros_fork=googlecartographer \
  --build-arg cartographer_ros_branch=master \
  .
docker push ${TAG}
