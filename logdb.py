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

import argparse
import json

import elasticsearch
import elasticsearch.helpers


class Handler(object):

    def __init__(self, url, index, queries, bulk_size=10000):
        self._url = url
        self._index = index
        self._es = elasticsearch.Elasticsearch([self._url])
        self._es.search()
        self._queries = queries
        self._bulk_size = bulk_size

    def bulk_delete(self, items):
        for item in items:
            item['_op_type'] = 'delete'
        ans = elasticsearch.helpers.bulk(self._es, items)
        print(ans)
        print('----------------------------------------')

    def bulk_insert(self, items):
        for item in items:
            item['_op_type'] = 'index'
        return elasticsearch.helpers.bulk(self._es, items)

    @staticmethod
    def _filter_usupported_ip_addr(item):
        ip_addr = item['_source'].get('ipAddress', '')
        if ip_addr is not None and ':' in ip_addr:
            item['_source']['ipAddress'] = None

    def process_query(self, query_id):
        q_conf = self._queries[query_id]
        query = {'query': q_conf['query'] if 'query' in q_conf else None}
        op = q_conf['op']
        print('query: %s' % (query,))
        print('op: %s' % (op,))
        ans = elasticsearch.helpers.scan(self._es, query=query, scroll='5m', index=self._index,
                                         doc_type=q_conf['type'])
        print(ans)
        print('running query ' + query_id)

        bulk = []
        fn = self.bulk_insert
        total_proc = 0
        for item in ans:
            if fn == self.bulk_insert:
                item['_index'] = op['target-index']
                self._filter_usupported_ip_addr(item)
                bulk.append(item)
            else:
                bulk.append({'_index': self._index, '_type': q_conf['type'], '_id': item['_id']})
            if len(bulk) == self._bulk_size:
                status = fn(bulk)
                total_proc += status[0]
                bulk = []
                print('total: %s' % total_proc)
        if len(bulk) > 0:
            status = fn(bulk)
            total_proc += status[0]
            print('total: %s' % total_proc)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Perform a bulk operation on CNK-logs data')
    parser.add_argument('conf_path', metavar='CONF_PATH', type=str, help='Path to a config file')
    parser.add_argument('query_id', metavar='QUERY_ID', type=str, help='A query identifier (as defined in config)')

    args = parser.parse_args()

    with open(args.conf_path, 'rb') as f:
        conf = json.load(f)
    handler = Handler(conf['url'], conf['index'], conf.get('queries', {}), bulk_size=2000)
    handler.process_query(args.query_id)






