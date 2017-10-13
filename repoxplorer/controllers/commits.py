# Copyright 2017, Fabien Boucher
# Copyright 2017, Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import hashlib

from datetime import datetime

from pecan import conf
from pecan import expose

from repoxplorer import index
from repoxplorer.controllers import utils
from repoxplorer.index.commits import Commits
from repoxplorer.index.commits import PROPERTIES
from repoxplorer.index.projects import Projects
from repoxplorer.index.contributors import Contributors

indexname = 'repoxplorer'
xorkey = conf.get('xorkey') or 'default'


class CommitsController(object):

    @expose('json')
    def commits(self, pid=None, tid=None, cid=None, gid=None,
                start=0, limit=10,
                dfrom=None, dto=None, inc_merge_commit=None,
                inc_repos=None, metadata="", exc_groups=None):

        c = Commits(index.Connector(index=indexname))
        projects_index = Projects()
        idents = Contributors()

        query_kwargs = utils.resolv_filters(
            projects_index, idents, pid, tid, cid, gid,
            dfrom, dto, inc_repos, inc_merge_commit,
            metadata, exc_groups)
        query_kwargs.update(
            {'start': start, 'limit': limit})

        resp = c.get_commits(**query_kwargs)

        for cmt in resp[2]:
            # Get extra metadata keys
            extra = set(cmt.keys()) - set(PROPERTIES.keys())
            cmt['metadata'] = list(extra)
            # Compute link to access commit diff based on the
            # URL template provided in projects.yaml
            cmt['gitwebs'] = [projects_index.get_gitweb_link(
                              ":".join(p.split(':')[0:-1])) %
                              {'sha': cmt['sha']} for
                              p in cmt['repos']]
            # Remove to verbose details mentionning this commit belong
            # to repos not included in the search
            # Also remove the URI part
            cmt['repos'] = [":".join(p.split(':')[-2:]) for
                            p in cmt['repos']]
            # Request the ident index to fetch author/committer name/email
            for elm in ('author', 'committer'):
                _, c_data = idents.get_ident_by_email(cmt['%s_email' % elm])
                cmt['%s_email' % elm] = c_data['default-email']
                if c_data['name']:
                    cmt['%s_name' % elm] = c_data['name']
            # Convert the TTL to something human readable
            cmt['ttl'] = str((datetime.fromtimestamp(cmt['ttl']) -
                              datetime.fromtimestamp(0)))
            cmt['author_gravatar'] = \
                hashlib.md5(cmt['author_email']).hexdigest()
            cmt['committer_gravatar'] = \
                hashlib.md5(cmt['committer_email']).hexdigest()
            if len(cmt['commit_msg']) > 80:
                cmt['commit_msg'] = cmt['commit_msg'][0:76] + '...'
            # Add cid and ccid
            cmt['cid'] = utils.encrypt(xorkey, cmt['author_email'])
            cmt['ccid'] = utils.encrypt(xorkey, cmt['committer_email'])
            # Remove email details
            del cmt['author_email']
            del cmt['committer_email']
        return resp
