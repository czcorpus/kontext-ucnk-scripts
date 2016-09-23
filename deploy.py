# Copyright (c) 2016 Charles University in Prague, Faculty of Arts,
#                    Institute of the Czech National Corpus
# Copyright (c) 2016 Tomas Machalek <tomas.machalek@gmail.com>
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
Required config:
{
    'appDir': '/path/to/the/web/application',
    'workingDir': '/path/to/working/dir/for/git/repo',
    'archiveDir': '/path/to/store/all/the/installed/versions',
    "gitUrl": "git_repository_URL"
    'gitBranch': 'used_git_branch',
    'gitRemote': 'git_remote_identifier',
}
"""

from datetime import datetime
from functools import wraps
import os
import json
import subprocess
import platform
import re
import argparse

DEFAULT_DATETIME_FORMAT = '%Y-%m-%d-%H-%M-%S'
FILES = ['cmpltmpl', 'lib', 'locale', 'public', 'scripts', 'package.json', 'worker.py']
DEPLOY_MESSAGE_FILE = '.deploy_info'
FORBIDDEN_DIRS = ['/', '/bin', '/boot', '/dev', '/etc', '/home', '/lib', '/lib64', '/media', '/mnt',
                  '/opt', '/proc', '/root', '/run', '/sbin', '/srv', '/sys', '/tmp', '/usr', '/var']


class Configuration(object):

    @staticmethod
    def _is_abs_path(s):
        # Windows detection is just for an internal testing
        # (the script is still only for Linux, BSD and the like)
        if platform.system() != 'Windows':
            return s.startswith('/')
        else:
            return re.match(r'[a-zA-Z]:\\', s) is not None

    def __init__(self, conf_path):
        keys = ['appConfigDir', 'workingDir', 'archiveDir', 'appDir']
        with open(conf_path, 'rb') as fr:
            data = json.load(fr)
        for item in keys:
            p = os.path.realpath(data[item])
            print(p)
            if sum(1 if p == x else 0 for x in FORBIDDEN_DIRS) > 0:
                raise ConfigError('%s cannot be set to forbidden value %s' % (item, p))
            elif not self._is_abs_path(p):
                raise ConfigError('%s path must be absolute' % (item,))
            elif not os.path.isdir(p):
                raise ConfigError('Path %s (%s) does not exist.' % (p, item))
        self._data = data

    @property
    def app_dir(self):
        return os.path.realpath(self._data['appDir'])

    @property
    def working_dir(self):
        return os.path.realpath(self._data['workingDir'])

    @property
    def archive_dir(self):
        return os.path.realpath(self._data['archiveDir'])

    @property
    def app_config_dir(self):
        return os.path.realpath(self._data['appConfigDir'])

    @property
    def git_url(self):
        return self._data['gitUrl']

    @property
    def git_branch(self):
        return self._data['gitBranch']

    @property
    def git_remote(self):
        return self._data['gitRemote']


class ConfigError(Exception):
    pass


class ShellCommandError(Exception):
    pass


class InputError(Exception):
    pass


def description(text):
    def decor(fn):
        @wraps(fn)
        def wrapper(*args, **kw):
            print('\n')
            print(70 * '-')
            print('| %s%s|' % (text, max(0, 67 - len(text)) * ' '))
            print(70 * '-')
            return fn(*args, **kw)
        return wrapper
    return decor


class Deployer(object):
    """
    Args:
        conf (Configuration): deployment configuration
    """

    def __init__(self, conf):
        self._conf = conf

    def shell_cmd(self, *args, **kw):
        """
        Args:
            args(list of str): command line arguments
        Returns:
            subprocess.Popen
        """
        p = subprocess.Popen(args, cwd=self._conf.working_dir, env=os.environ.copy(), **kw)
        if p.wait() != 0:
            raise ShellCommandError('Failed to process action: %s' % ' '.join(args))
        return p

    @description('Creating archive directory for the new version')
    def create_archive(self, date):
        """

        Args:
            date(datetime):

        Returns:
            str: path to the current archive item
        """
        arch_path = os.path.join(self._conf.archive_dir, date.strftime(DEFAULT_DATETIME_FORMAT))
        if not os.path.isdir(arch_path):
            os.makedirs(arch_path)
        return arch_path

    @description('Copying built project to the archive')
    def copy_app_to_archive(self, arch_path):
        """
        Args:
            arch_path (str): path to archive subdirectory

        Returns:
            None

        Raises:
            ShellCommandError
        """
        for item in FILES:
            src_path = os.path.join(self._conf.working_dir, item)
            self.shell_cmd('cp', '-r', '-p', src_path, arch_path)

    @description('Updating working config.xml')
    def update_working_conf(self):
        """
        Raises:
            ShellCommandError
        """
        self.shell_cmd('cp', '-p', os.path.join(self._conf.app_config_dir, 'config.xml'),
                       os.path.join(self._conf.working_dir, 'conf'))

    @description('Copying configuration to the archive')
    def copy_configuration(self, arch_path):
        """
        Args:
            arch_path (str): path to archive subdirectory
        Raises:
            ShellCommandError
        """
        self.shell_cmd('cp', '-r', '-p', self._conf.app_config_dir, arch_path)

    @description('Updating data from repository')
    def update_from_repository(self):
        working_dir = self._conf.working_dir
        if not os.path.isdir(working_dir):
            os.makedirs(working_dir)

        if not os.path.isdir(os.path.join(working_dir, '.git')):
            self.shell_cmd('git', 'clone', self._conf.git_url, '.')
        else:
            self.shell_cmd('git', 'checkout', self._conf.git_branch)
            self.shell_cmd('git', 'fetch', self._conf.git_remote)
            self.shell_cmd('git', 'merge', '%s/%s' % (self._conf.git_remote, self._conf.git_branch))

    @description('Writing information about used GIT commit')
    def record_deployment_info(self, arch_path, message):
        """
        Args:
            arch_path (str): path to an archive
        """
        p = self.shell_cmd('git', 'log', '-1', '--oneline', stdout=subprocess.PIPE)
        commit_info = p.stdout.read().strip()
        with open(os.path.join(arch_path, DEPLOY_MESSAGE_FILE), 'wb') as fw:
            if message:
                fw.write(message + '\n\n')
            fw.write(commit_info + '\n')

    @description('Building project using Grunt.js')
    def build_project(self):
        if not os.path.isdir(os.path.join(self._conf.working_dir, 'node_modules')):
            self.shell_cmd('npm', 'install')
        self.shell_cmd('grunt', 'production')

    @description('Removing current deployment')
    def remove_current_deployment(self):
        self.shell_cmd('rm -rf %s' % os.path.join(self._conf.app_dir, '*'), shell=True)
        self.shell_cmd('rm -rf %s' % os.path.join(self._conf.app_dir, '.[a-z]*'), shell=True)

    @description('Deploying new version')
    def deploy_new_version(self, arch_path):
        """
        Args:
            arch_path (str): path to an archive
        """
        for item in FILES + [DEPLOY_MESSAGE_FILE]:
            self.shell_cmd('cp', '-r', '-p', os.path.join(arch_path, item), self._conf.app_dir)

    def run_all(self, date, message):
        """
        Args:
            date (datetime): a date used to create a new archive
        """
        self.update_from_repository()
        self.update_working_conf()
        self.build_project()
        arch_path = self.create_archive(date)
        self.copy_configuration(arch_path)
        self.record_deployment_info(arch_path, message)
        self.copy_app_to_archive(arch_path)
        self.remove_current_deployment()
        self.deploy_new_version(arch_path)

    def from_archive(self, archive_id):
        """
        Args:
            archive_id (str): an ID of an archived item to be deployed
        """
        arch_path = os.path.join(self._conf.archive_dir, archive_id)
        self.remove_current_deployment()
        self.deploy_new_version(arch_path)
        with open(os.path.join(arch_path, DEPLOY_MESSAGE_FILE), 'rb') as fr:
            print('\nDeployment information:\n%s' % fr.read())


def list_archive(conf):
    """
    Args:
        conf (Configuration): script conf
    """
    print('archived deployments:')
    print(conf.archive_dir)
    for item in os.listdir(conf.archive_dir):
        print('\t{0}'.format(item))


def find_matching_archive(conf, arch_id):
    """
    Args:
        conf (Configuration): script configuration
        arch_id: an archive ID (even partial prefix)

    Returns:
        str: an ID of matching archive or None

    Raises:
        InputError: in case of ambiguous search (one exact match is accepted only)

    """
    avail_archives = os.listdir(conf.archive_dir)
    ans = None
    for item in avail_archives:
        if item.startswith(arch_id):
            if ans is None:
                ans = item
            else:
                raise InputError('Ambiguous archive ID search. Please specify a more concrete value.')
    return ans


if __name__ == '__main__':
    argp = argparse.ArgumentParser(description='UCNK KonText deployment script')
    argp.add_argument('action', metavar='ACTION', help='Action to perform (deploy, list)')
    argp.add_argument('archive_id', metavar='ARCHIVE_ID', nargs='?',
                      default='new', help='Archive identifier (default is *new*)')
    argp.add_argument('-c', '--config-path', type=str,
                      help='Path to a JSON config file (default is *deploy.json* in script\'s directory)')
    argp.add_argument('-m', '--message', type=str,
                      help='A custom message stored in generated archive (.deployinfo)')
    args = argp.parse_args()
    try:
        if args.config_path is None:
            conf_path = os.path.join(os.path.dirname(__file__), './deploy.json')
        else:
            conf_path = args.config_path
        conf = Configuration(conf_path)

        if args.action == 'deploy':
            d = Deployer(conf)
            if args.archive_id == 'new':
                print('installing latest version from %s' % conf.git_branch)
                d.run_all(datetime.now(), args.message)
            else:
                m = find_matching_archive(conf, args.archive_id)
                if m is not None:
                    print('installing from archive: %s' % m)
                    d.from_archive(m)
                else:
                    InputError('No matching archive for %s' % args.archive_id)
        elif args.action == 'list':
            list_archive(conf)
        else:
            raise Exception('Unknown action "%s" (use one of: deploy, list)' % (args.action,))
    except ConfigError as e:
        print('\nConfiguration error: %s\n' % e)
    except Exception as e:
        print('\nERROR: %s\n' % e)
    print('\n')

