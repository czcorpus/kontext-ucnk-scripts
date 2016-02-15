# Copyright 2016 Institute of the Czech National Corpus
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
required configuration JSON:

{
    "srcDir": "/var/log/kontext",
    "dstDir": "/mnt/archive",
    "fileName": "application.log",
    "rotationPattern": ".(\\d+)",
    "moveIfOlderThanSecs": 86400,
    "worklogPath": "/path/to/worklog.txt"
}
"""

import sys
import os
import time
from datetime import datetime
import re
import shutil
import hashlib
import json


class Conf(object):

    def __init__(self, path):
        self._data = json.load(open(path, 'rb'))

    @property
    def src_dir(self):
        return self._data['srcDir']

    @property
    def dst_dir(self):
        return self._data['dstDir']

    @property
    def file_name(self):
        return self._data['fileName']

    @property
    def rotation_pattern(self):
        return self._data['rotationPattern']

    @property
    def move_if_older_than_secs(self):
        return self._data['moveIfOlderThanSecs']

    @property
    def worklog_path(self):
        return self._data['worklogPath']


class Archiver(object):

    def __init__(self, conf):
        self._conf = conf

    def update_worklog(self, data):
        with open(self._conf.worklog_path, 'a') as f:
            for item in data:
                f.write(json.dumps(item) + '\n')

    @staticmethod
    def current_timestamp():
        return time.mktime(datetime.now().timetuple())

    @staticmethod
    def get_hash(file_path):
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def is_log_file(self, name):
        return bool(re.match('%s(%s)?' % (self._conf.file_name, self._conf.rotation_pattern), name))

    def can_be_archived(self, path):
        return (os.path.isfile(path) and
                self.current_timestamp() - os.path.getmtime(path) > self._conf.move_if_older_than_secs and
                os.path.basename(path) != self._conf.file_name)

    def archive(self, file_path, dest_dir):
        ans = {'datetime': datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}
        suff = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y%m%d%H%M')
        target_path = os.path.join(dest_dir,
                                   os.path.join(dest_dir, '%s.%s' % (os.path.basename(file_path), suff)))
        try:
            ans['checksum'] = self.get_hash(file_path)
            shutil.move(file_path, target_path)
        except IOError as e:
            ans['error'] = str(e)
        ans['src'] = file_path
        ans['dst'] = target_path
        return ans

    def process_dir(self):
        log = []
        for item in os.listdir(self._conf.src_dir):
            abs_path = os.path.join(self._conf.src_dir, item)
            if self.is_log_file(item) and self.can_be_archived(abs_path):
                log.append(self.archive(abs_path, self._conf.dst_dir))
        self.update_worklog(log)


if __name__ == '__main__':
    if len(sys.argv) < 2 or not os.path.isfile(sys.argv[1]):
        raise Exception('A path to a configuration JSON file must be specified')

    conf = Conf(sys.argv[1])
    if not os.path.isdir(os.path.dirname(conf.worklog_path)):
        raise Exception('Worklog directory %s does not exist.' % (os.path.dirname(conf.worklog_path),))
    if not os.path.isdir(conf.dst_dir):
        raise Exception('Destination directory %s does not exist' % (conf.dst_dir,))
    arch = Archiver(conf)
    arch.process_dir()
