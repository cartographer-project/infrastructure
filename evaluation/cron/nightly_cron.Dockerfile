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

FROM debian

RUN apt-get update && \
    apt-get install -y sudo && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get -y install curl python-pip


# Cloud SDK layer
ENV CLOUDSDK_CORE_DISABLE_PROMPTS 1
ENV PATH /opt/google-cloud-sdk/bin:$PATH

# Cluster information:
ENV CLUSTER carto-evaluation
ENV CLUSTER_ZONE us-west1-a


# Install Google Cloud Components
RUN curl https://sdk.cloud.google.com | bash && \
    mv /root/google-cloud-sdk /opt && \
    gcloud components install bq && \
    gcloud components install kubectl && \
    pip install --upgrade absl-py && \
    pip install --upgrade pytz && \
    pip install --upgrade kubernetes && \
    pip install --upgrade google-cloud-bigquery && \
    pip install --upgrade google-cloud-storage

RUN gcloud config set project cartographer-141408

WORKDIR /


COPY evaluation_pipeline /infrastructure/evaluation/evaluation_pipeline
COPY k8s_job_creator /infrastructure/evaluation/k8s_job_creator
COPY dataset_lists /infrastructure/evaluation/dataset_lists
COPY scripts /infrastructure/evaluation/scripts
COPY Dockerfile /infrastructure/evaluation/Dockerfile
COPY cron/cloud_build.yaml /infrastructure/evaluation/cloud_build.yaml
COPY cron/nightly_tasks.sh /infrastructure/evaluation/nightly_tasks.sh

ENTRYPOINT /infrastructure/evaluation/nightly_tasks.sh
