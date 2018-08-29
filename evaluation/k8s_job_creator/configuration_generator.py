""" Functions for generating configuration files from parameter sweeps.

Set of helper functions to generate Lua configuration files for cartographer,
for parameter sweeps.
"""

from __future__ import absolute_import

from absl import logging
from google.cloud import storage


def upload_to_cloud_bucket(src_file, destination_bucket, destination,
                           secret_json):
  """ Helper for uploading a file to cloud storage.

  """
  client = storage.Client.from_service_account_json(secret_json)
  try:
    bucket = client.bucket(destination_bucket)
    logging.info('Uploading %s files', src_file)
    blob = bucket.blob(destination)
    blob.upload_from_filename(src_file)
  except google.cloud.exceptions.NotFound:
    logging.error('Cloud bucket not found: %s.', bucket_name)
    return False
  return True


def load_sweep_file(filename):
  """ Loads file and returns single lines split by empty space.

  """
  with open(filename, 'rb') as f:
    for line in f:
      items = line.split(' ')
      if len(items) > 1:
        yield items


def load_base_config_file(filename):
  """ Loads file into list of lines, removing the "return options" line.

  """
  with open(filename, 'r') as cfg_file:
    return [l for l in cfg_file.readlines() if not 'return options' in l]


def write_config_file(base, swept_cfgs, output_file):
  """ Writes a lua configuration file.

  First writes the base configuration lines and then the parameter overrides
  specified in the swept_cfgs dictionary, which maps parameter names to
  parameter values.
  """
  with open(output_file, 'wt') as out:
    out.writelines(base)
    for param, value in swept_cfgs.iteritems():
      out.write('{} = {}\n'.format(param, value))
    out.write('return options\n')


class ParameterSweep:
  """ A sweep for a single parameter.

  Represents a single parameter and the values it should take in the sweep.
  """

  def __init__(self, parameter_with_values):
    self._param_name = parameter_with_values[0].strip()
    self._values = [v.strip() for v in parameter_with_values[1:]]

  def dimension(self):
    return len(self._values)

  def name(self):
    return self._param_name

  def value_for_index(self, index):
    return self._values[index]


def sweep_parameters(sweep_file_name):
  """ Sweeps through all parameter combinations.

  Yields a dictionary with <name : value> items in each iteration.
  """
  parameter_sweep = [
      ParameterSweep(x) for x in load_sweep_file(sweep_file_name)
  ]
  current_index = [0 for _ in parameter_sweep]

  while current_index[0] < parameter_sweep[0].dimension():
    config_instance = dict()
    for i, p in enumerate(parameter_sweep):
      config_instance[p.name()] = p.value_for_index(current_index[i])
    yield config_instance

    increment_next = True
    idx = len(parameter_sweep) - 1
    while increment_next and idx >= 0:
      current_index[idx] += 1
      if current_index[idx] >= parameter_sweep[idx].dimension():
        if idx != 0:
          current_index[idx] = 0
        increment_next = True
      else:
        increment_next = False
      idx -= 1
