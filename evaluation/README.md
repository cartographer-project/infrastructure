# Kubernetes based Evaluation Pipeline
This folder contains files needed to setup a kubernetes based evaluation
pipeleline on GCP.

## Source tree overview

| File / Folder                    | Description                                                               |
| :------------------------------- | :------------------------------------------------------------------------ |
| **`cron`**                       | folder with files for cron job (docker image, k8s configs, ...).          |
| **`dataset_lists`**              | CSV files with datasets that shall be processed.                          |
| **`evaluation_pipeline`**        | Python script that will perform the required steps for a single bag file. |
| **`k8s_job_creator`**            | Python tool(s), using the k8s client API for creating k8s jobs.           |
| **`scripts`**                    | scripts to be used within the Docker image(s).                            |
| **`evaluation_base.Dockerfile`** | Base docker image for the evaluation (mainly to speed up compilation).    |
| **`Dockerfile`**                 | The docker image that will be used for each evaluation pod.               |
| **`update_eval_base_image.sh`**  | Helper script for updating the base image (build, tag and upload).        |
| **`update_eval_image.sh`**       | Helper script for updating the evaluation image.                          |
