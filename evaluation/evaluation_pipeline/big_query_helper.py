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
"""Helpers for pushing results into a big query table.

Helper classes and functions for pushing data into big query tables.
"""

from __future__ import absolute_import
from absl import logging

from google.cloud import bigquery
import csv


class BigQueryHelper(object):

  def __init__(self, dataset, secret_json):
    self._client = bigquery.Client.from_service_account_json(secret_json)
    self._dataset = self._client.dataset(dataset)

  def insert_rows(self, table_name, rows):
    """rows will should be a list of dictionaries (one per row).

    During insertion, the dictionary keys will be used to find the
    corresponding field of the schema.
    """
    table_ref = self._dataset.table(table_name)
    try:
      table = self._client.get_table(table_ref)
      errors = self._client.insert_rows(table, rows)
      if errors:
        for e in errors:
          logging.error('Failure when inserting row: %s', str(e))
      else:
        logging.info('Successfully inserted %d rows into %s', len(rows),
                     table_name)
    except ValueError as e:
      logging.error('Could not insert into requested table %s. Error: %s',
                    table_name, e)


def store_in_bigquery(scratch_dir, experiment_id, job_uuid, bag_file,
                      secret_json, creation_date, tags):
  """Stores result data into bigquery table(s).
  """
  relations_csv = '{}/{}.pbstream.relation_metrics.csv'.format(
      scratch_dir, bag_file)

  logging.info('Storing relations from CSV %s into bigquery table.',
               relations_csv)

  rows = []
  with open(relations_csv, 'rb') as file:
    reader = csv.DictReader(file)
    rows = [r for r in reader]

  logging.info('Found %d rows in CSV.', len(rows))
  # add additional columns:
  for r in rows:
    r['experiment_id'] = experiment_id
    r['job_uuid'] = job_uuid
    r['datetime'] = creation_date
    r['bag_file'] = bag_file
    if tags:
      r['tags'] = tags

  dataset = 'cartographer_evaluation'
  helper = BigQueryHelper(dataset, secret_json)
  table = 'loop_closure_relations'
  helper.insert_rows(table, rows)
