# -*- coding: utf-8 -*-

# Copyright 2013 Fanficdownloader team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Software: eFiction
from base_efiction_adapter import BaseEfictionAdapter

def getClass():
    return TrekiverseOrgAdapter

class TrekiverseOrgAdapter(BaseEfictionAdapter):

    @staticmethod
    def getSiteDomain():
        return 'trekiverse.org'

    @classmethod
    def getPathToArchive(cls):
        return '/efiction'

    @classmethod
    def getSiteAbbrev(cls):
        return 'trkvs'

    @classmethod
    def getDateFormat(cls):
        return "%d %b %Y"

    @classmethod
    def getEncoding(cls):
        return ["ISO-8859-1", "utf8"]

    def handleMetadataPair(self, key, value):
        if key == 'Awards':
            self.story.setMetadata('awards', value)
        else:
            super(TrekiverseOrgAdapter, self).handleMetadataPair(key, value)
