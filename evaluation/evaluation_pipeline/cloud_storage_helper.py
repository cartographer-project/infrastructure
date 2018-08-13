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
""" Helper functions to upload and download files from / to cloud storage.

"""

from __future__ import absolute_import
from absl import logging

import google.cloud.exceptions
from google.cloud import storage

import os


def download_from_cloud_storage(secret_json, bucket_name, file_path,
                                destination_path):
  """Downloads the the file from cloud storage to local file system.
  """
  client = storage.Client.from_service_account_json(secret_json)
  try:
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_path)
    if blob == None:
      logging.error('File not found: %s.', file_path)
      return False

    with open(destination_path, 'wb') as file_obj:
      blob.download_to_file(file_obj)
  except google.cloud.exceptions.NotFound:
    logging.error('Cloud bucket not found: %s.', bucket_name)
    return False
  return True


def path_to_blob(path):
  """ Converts `gs://bucket/path/to/file` into bucket and file within bucket

  Returns tuple: bucket, path/to/file. If the path is not a valid cloud storage
  path, the function returns `None, None`
  """
  gs_prefix = 'gs://'
  if not path.startswith(gs_prefix):
    return None, None
  path_without_prefix = path.strip()[len(gs_prefix):]

  # Split into bucket and file path.
  bucket_end = path_without_prefix.find('/')
  # we should have at least 3 characters (b/f) for a valid blob url.
  if bucket_end < 1:
    return None, None
  if (len(path_without_prefix) - bucket_end - 1) < 1:
    return None, None

  bucket = path_without_prefix[:bucket_end]
  path_in_bucket = path_without_prefix[bucket_end + 1:]
  return bucket, path_in_bucket


def upload_artifacts(artifacts_directory,
                     destination_bucket,
                     destination_path,
                     secret_json,
                     skip_extensions=('.bag')):
  logging.info('Uploading artifacts to %s', destination_bucket)
  client = storage.Client.from_service_account_json(secret_json)
  try:
    bucket = client.bucket(destination_bucket)
    for root, d, files in os.walk(artifacts_directory):
      logging.info('Uploading %d files', len(files))
      for f in files:
        if f.lower().endswith(skip_extensions):
          continue

        print('uploading {}/{} to {}/{}'.format(root, f, destination_path, f))
        blob = bucket.blob('{}/{}'.format(destination_path, f))
        blob.upload_from_filename('{}/{}'.format(root, f))
  except google.cloud.exceptions.NotFound:
    logging.error('Cloud bucket not found: %s.', bucket_name)
    return False
  return True
