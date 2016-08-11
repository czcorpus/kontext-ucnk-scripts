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

import unittest
import os
import shutil
from datetime import datetime

import deploy

APP_DIR = '/tmp/deploytest/app'
WORKING_DIR = '/tmp/deploytest/working'
ARCHIVE_DIR = '/tmp/deploytest/archive'
APP_CONF_DIR = '/tmp/deploytest/app_conf'
GIT_REPO_URL = 'https://github.com/czcorpus/kontext.git'
GIT_BRANCH = 'master'
GIT_REMOTE = 'origin'
KONTEXT_CONF_DATA = {
    'config.xml': '<kontext><theme /><global /><corpora /></kontext>',
    'corpora.xml': '<kontext><corpora /></kontext>',
    'tagsets.xml': '<kontext></tagsets /></kontext>',
    'main-menu.json': '{}'
}


def rmfile(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.unlink(path)


def create_kontext_conf(dst_dir):
    for item in deploy.Configuration.KONTEXT_CONF_FILES:
        with open(os.path.join(dst_dir, item), 'wb') as fw:
            fw.write(KONTEXT_CONF_DATA.get(item, 'FOO = "bar"\n'))


def clean_dirs():
    if os.path.exists(APP_DIR):
        rmfile(APP_DIR)
    if os.path.exists(WORKING_DIR):
        rmfile(WORKING_DIR)
    if os.path.exists(ARCHIVE_DIR):
        rmfile(ARCHIVE_DIR)
    if os.path.exists(APP_CONF_DIR):
        rmfile(APP_CONF_DIR)


def create_dirs():
    clean_dirs()
    if not os.path.isdir(APP_DIR):
        os.makedirs(APP_DIR)
    if not os.path.isdir(WORKING_DIR):
        os.makedirs(WORKING_DIR)
        os.makedirs(os.path.join(WORKING_DIR, 'conf'))
        for d in ('cmpltmpl', 'lib', 'locale', 'public', 'scripts'):
            os.makedirs(os.path.join(WORKING_DIR, d))
        with open(os.path.join(WORKING_DIR, 'lib/foo.py'), 'wb') as fw:
            fw.write('APP = "kontext"\nFILE = "foo"\n')
        with open(os.path.join(WORKING_DIR, 'package.json'), 'wb') as fw:
            fw.write('{}')
        with open(os.path.join(WORKING_DIR, 'worker.py'), 'wb') as fw:
            fw.write('APP = "worker"\n')
    if not os.path.isdir(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
    if not os.path.isdir(APP_CONF_DIR):
        os.makedirs(APP_CONF_DIR)
        create_kontext_conf(APP_CONF_DIR)


def get_conf():
    return {
        'appDir': APP_DIR,
        'workingDir': WORKING_DIR,
        'archiveDir': ARCHIVE_DIR,
        'appConfigDir': APP_CONF_DIR,
        'gitUrl': GIT_REPO_URL,
        'gitBranch': GIT_BRANCH,
        'gitRemote': GIT_REMOTE
    }


class ConfigurationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        clean_dirs()

    def test_non_existing_workdir(self):
        for item in [APP_DIR, WORKING_DIR, ARCHIVE_DIR, APP_CONF_DIR]:
            create_dirs()
            rmfile(item)
            with self.assertRaises(deploy.ConfigError):
                deploy.Configuration(get_conf(), skip_remote_checks=True)

    def test_relative_path(self):
        create_dirs()
        rev_conf = dict((v, k) for k, v in get_conf().items())
        tmp = {APP_DIR: 'deployment/app', WORKING_DIR: 'deployment/working',
               ARCHIVE_DIR: 'deployment/archive', APP_CONF_DIR: 'deployment/app_conf'}
        for path in tmp.keys():
            conf = get_conf()
            conf[rev_conf[path]] = tmp[path]
            with self.assertRaises(deploy.ConfigError):
                deploy.Configuration(conf, skip_remote_checks=True)

    def test_forbidden_path(self):
        create_dirs()
        rev_conf = dict((v, k) for k, v in get_conf().items())
        tmp = [APP_DIR, WORKING_DIR, ARCHIVE_DIR, APP_CONF_DIR]
        root_items = ['/%s' % x for x in os.listdir('/')]
        for path in tmp:
            for root_item in root_items:
                conf = get_conf()
                conf[rev_conf[path]] = root_item
                with self.assertRaises(deploy.ConfigError):
                    deploy.Configuration(conf, skip_remote_checks=True)

    def test_invalid_git_url(self):
        create_dirs()
        conf_data = get_conf()
        conf_data['gitUrl'] = 'http://foo.something'
        with self.assertRaises(deploy.ConfigError):
            deploy.Configuration(conf_data)

    def test_ok_config(self):
        create_dirs()
        conf = deploy.Configuration(get_conf())
        self.assertEqual(APP_DIR, conf.app_dir)
        self.assertEqual(WORKING_DIR, conf.working_dir)
        self.assertEqual(ARCHIVE_DIR, conf.archive_dir)
        self.assertEqual(APP_CONF_DIR, conf.app_config_dir)
        self.assertEqual(GIT_REPO_URL, conf.git_url)
        self.assertEqual(GIT_BRANCH, conf.git_branch)
        self.assertEqual(GIT_REMOTE, conf.git_remote)

    def test_empty_config(self):
        with self.assertRaises(TypeError):
            deploy.Configuration(None)
        with self.assertRaises(KeyError):
            deploy.Configuration({})

    def test_kontext_conf_remap(self):
        create_dirs()
        conf_data = get_conf()
        conf_data['kontextConfAliases'] = {'tagsets.xml': 'tag.xml'}
        conf = deploy.Configuration(conf_data)
        self.assertTrue('tag.xml' in conf.kontext_conf_files)
        self.assertFalse('tagsets.xml' in conf.kontext_conf_files)


class DeployTest(unittest.TestCase):

    def test_update_working_conf(self):
        create_dirs()
        conf = deploy.Configuration(get_conf())
        dp = deploy.Deployer(conf)
        dp.update_working_conf()
        conf_copy_path = os.path.join(WORKING_DIR, 'conf/config.xml')
        self.assertTrue(os.path.isfile(conf_copy_path))
        with open(conf_copy_path, 'rb') as fr:
            self.assertEqual(KONTEXT_CONF_DATA['config.xml'], fr.read())

    def test_create_archive(self):
        create_dirs()
        conf = deploy.Configuration(get_conf())
        dp = deploy.Deployer(conf)
        date_items = (2001, 9, 20, 12, 30, 41)
        arch_path = dp.create_archive(datetime(*date_items))
        exp_arch_path = os.path.join(ARCHIVE_DIR, '-'.join('%02d' % x for x in date_items))
        self.assertTrue(os.path.isdir(exp_arch_path))
        self.assertEqual(exp_arch_path, arch_path)

    def test_copy_configuration(self):
        create_dirs()
        conf = deploy.Configuration(get_conf())
        dp = deploy.Deployer(conf)
        date_items = (2001, 9, 20, 12, 30, 41)
        arch_path = dp.create_archive(datetime(*date_items))
        dp.copy_configuration(arch_path)
        exp_arch_path = os.path.join(ARCHIVE_DIR, '-'.join('%02d' % x for x in date_items))
        for item in os.listdir(exp_arch_path):
            self.assertTrue(item in deploy.Configuration.KONTEXT_CONF_FILES)

    def test_copy_app_to_archive(self):
        create_dirs()
        conf = deploy.Configuration(get_conf())
        dp = deploy.Deployer(conf)
        date_items = (2001, 9, 20, 12, 30, 41)
        arch_path = os.path.join(ARCHIVE_DIR, '-'.join('%02d' % x for x in date_items))
        os.makedirs(arch_path)
        dp.copy_app_to_archive(arch_path)
        for item in deploy.FILES:
            self.assertTrue(os.path.exists(os.path.join(arch_path, item)))

    def test_remove_current_deployment(self):
        create_dirs()
        os.makedirs(os.path.join(APP_DIR, 'foo/bar'))
        with open(os.path.join(APP_DIR, 'foo/bar/test.txt'), 'wb') as fw:
            fw.write('lorem ipsum dolor sit amet...')
        with open(os.path.join(APP_DIR, 'package.json'), 'wb') as fw:
            fw.write('{}')
        conf = deploy.Configuration(get_conf())
        dp = deploy.Deployer(conf)
        dp.remove_current_deployment()
        self.assertEqual(0, len(os.listdir(APP_DIR)))

    def test_deploy_new_version(self):
        pass # TODO


if __name__ == '__main__':
    unittest.main()
