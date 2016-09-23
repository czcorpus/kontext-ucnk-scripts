#!/usr/bin/env python
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
    'appConfigDir': '/path/to/kontext/conf/dir',
    'gitUrl': 'git_repository_URL',
    'gitBranch': 'used_git_branch',
    'gitRemote': 'git_remote_identifier'
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
import urllib2

GIT_URL_TEST_TIMEOUT = 5
DEFAULT_DATETIME_FORMAT = '%Y-%m-%d-%H-%M-%S'
FILES = ('cmpltmpl', 'lib', 'locale', 'public', 'scripts', 'package.json', 'worker.py')
DEPLOY_MESSAGE_FILE = '.deploy_info'
INVALIDATION_FILE = '.invalid'
APP_DIR = 'appDir'
WORKING_DIR = 'workingDir'
ARCHIVE_DIR = 'archiveDir'
APP_CONFIG_DIR = 'appConfigDir'
GIT_URL = 'gitUrl'
GIT_BRANCH = 'gitBranch'
GIT_REMOTE = 'gitRemote'
KONTEXT_CONF_ALIASES = 'kontextConfAliases'
KONTEXT_CONF_CUSTOM = 'kontextConfCustom'


class InvalidatedArchiveException(Exception):
    pass


class Configuration(object):
    """
    Args:
        data (dict): deserialized JSON configuration data
    """

    KONTEXT_CONF_FILES = (
        'beatconfig.py', 'celeryconfig.py', 'config.xml', 'corpora.xml', 'gunicorn-conf.py',
        'main-menu.json', 'tagsets.xml')

    @staticmethod
    def _is_forbidden_dir(path):
        tmp = os.path.realpath(path).split('/')
        return len(tmp) == 2 and tmp[0] == ''

    @staticmethod
    def _test_git_repo_url(url):
        try:
            ans = urllib2.urlopen(url, timeout=GIT_URL_TEST_TIMEOUT)
            if ans.code != 200:
                raise ConfigError('Unable to validate git repo url %s' % url)
        except urllib2.URLError:
            raise ConfigError('Unable to validate git repo url %s' % url)

    @staticmethod
    def _is_abs_path(s):
        # Windows detection is just for an internal testing
        # (the script is still only for Linux, BSD and the like)
        if platform.system() != 'Windows':
            return s.startswith('/')
        else:
            return re.match(r'[a-zA-Z]:\\', s) is not None

    def __init__(self, data, skip_remote_checks=False):
        keys = [APP_CONFIG_DIR, WORKING_DIR, ARCHIVE_DIR, APP_DIR]
        for item in keys:
            p = os.path.realpath(data[item])
            if self._is_forbidden_dir(p):
                raise ConfigError('%s cannot be set to forbidden value %s' % (item, p))
            elif not self._is_abs_path(p):
                raise ConfigError('%s path must be absolute' % (item,))
            elif not os.path.isdir(p):
                raise ConfigError('Path %s (%s) does not exist.' % (p, item))
        if not skip_remote_checks:
            self._test_git_repo_url(data[GIT_URL])
        self._kc_aliases = data.get(KONTEXT_CONF_ALIASES, {})
        self._kc_custom = data.get(KONTEXT_CONF_CUSTOM, [])
        self._data = data

    @property
    def kontext_conf_files(self):
        conf_files = self.KONTEXT_CONF_FILES + tuple(self._kc_custom)
        return [self._kc_aliases[k] if k in self._kc_aliases else k for k in conf_files]

    @property
    def app_dir(self):
        return os.path.realpath(self._data[APP_DIR])

    @property
    def working_dir(self):
        return os.path.realpath(self._data[WORKING_DIR])

    @property
    def archive_dir(self):
        return os.path.realpath(self._data[ARCHIVE_DIR])

    @property
    def app_config_dir(self):
        return os.path.realpath(self._data[APP_CONFIG_DIR])

    @property
    def git_url(self):
        return self._data[GIT_URL]

    @property
    def git_branch(self):
        return self._data[GIT_BRANCH]

    @property
    def git_remote(self):
        return self._data[GIT_REMOTE]


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
        os.makedirs(os.path.join(arch_path, 'conf'))
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
        for item in self._conf.kontext_conf_files:
            src_path = os.path.join(self._conf.app_config_dir, item)
            dst_path = os.path.join(arch_path, 'conf', item)
            self.shell_cmd('cp', '-p', src_path, dst_path)

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
        for item in FILES + (DEPLOY_MESSAGE_FILE, 'conf'):
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


def invalidate_archive(conf, archive_id, message):
    archive_id = find_matching_archive(conf, archive_id)
    arch_path = os.path.join(conf.archive_dir, archive_id)
    with open(os.path.join(arch_path, INVALIDATION_FILE), 'w') as fw:
        fw.write(message + '\n')


def _test_archive_validity(conf, archive_id):
    flag_file_path = os.path.join(conf.archive_dir, archive_id, INVALIDATION_FILE)
    if os.path.isfile(flag_file_path):
        with open(flag_file_path, 'r') as fr:
            raise InvalidatedArchiveException('Archive marked as invalid. Reason: %s' % fr.read())


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
    if os.getuid() == 0:
        import sys
        print('Please do not run the script as root')
        sys.exit(1)
    argp = argparse.ArgumentParser(description='UCNK KonText deployment script')
    argp.add_argument('action', metavar='ACTION', help='Action to perform (deploy, list, invalidate)')
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
        with open(conf_path, 'rb') as fr:
            conf = Configuration(json.load(fr))

        if args.action == 'deploy':
            d = Deployer(conf)
            if args.archive_id == 'new':
                print('installing latest version from %s' % conf.git_branch)
                d.run_all(datetime.now(), args.message)
            else:
                m = find_matching_archive(conf, args.archive_id)
                _test_archive_validity(conf, m)
                if m is not None:
                    print('installing from archive: %s' % m)
                    d.from_archive(m)
                else:
                    InputError('No matching archive for %s' % args.archive_id)
        elif args.action == 'list':
            list_archive(conf)
        elif args.action == 'invalidate':
            invalidate_archive(conf, args.archive_id, args.message)
        else:
            raise Exception('Unknown action "%s" (use one of: deploy, list)' % (args.action,))
    except ConfigError as e:
        print('\nConfiguration error: %s\n' % e)
    except Exception as e:
        print('\nERROR: %s\n' % e)
    print('\n')

