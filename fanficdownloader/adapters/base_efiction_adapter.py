# -*- coding: utf-8 -*-

# Copyright 2014 Fanficdownloader team
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
# import time
# import urllib
import logging
logger = logging.getLogger(__name__)
import re
import urllib2

from .. import BeautifulSoup as bs
from ..htmlcleanup import stripHTML
from .. import exceptions as exceptions

from base_adapter import BaseSiteAdapter, makeDate

"""
This is a generic adapter for eFiction based archives (see
http://fanlore.org/wiki/List_of_eFiction_Archives for a list).

Most of them share common traits:
    * No HTTPS
    * 'www.' is optional
    * Default story template is 'viewstory.php' with arguments
        * 'sid' the storyId
        * 'chapter' for chapters (will be thrown away anyway by
           stripURLParameters in base_adapter
    Use Printable version which is easier to parse and has everything in one
    page and cache between extractChapterUrlsAndMetadata and getChapterText
"""

# PHP constants
_RUSERSONLY = 'Registered Users Only'
_NOSUCHACCOUNT = "There is no such account on our website"
_WRONGPASSWORD = "That password doesn't match the one in our database"
_USERACCOUNT = 'Member Account'

# Regular expressions
_REGEX_WARING_PARAM = re.compile("warning=(?P<warningId>\d+)")
_REGEX_CHAPTER_B = re.compile("^(?P<chapterId>\d+)\.")
_REGEX_CHAPTER_PARAM = re.compile("chapter=(?P<chapterId>\d+)$")
_REGEX_CHAPTER_FRAGMENT = re.compile("^#(?P<chapterId>\d+)$")
_REGEX_DOESNT_START_WITH_HTTP = re.compile("^(?!http)")

class BaseEfictionAdapter(BaseSiteAdapter):

    def __init__(self, config, url):
        BaseSiteAdapter.__init__(self, config, url)
        self.story.setMetadata('siteabbrev',self.getSiteAbbrev())
        self.decode = self.getEncoding()
        storyId = re.compile(self.getSiteURLPattern()).match(self.url).group('storyId')
        self.story.setMetadata('storyId', storyId)
        self._setURL(self.getViewStoryUrl(storyId))
        self.triedLoggingIn = False
        self.triedAcceptWarnings = False
        self.username = "NoneGiven" # if left empty, site doesn't return any message at all.

    @classmethod
    def getAcceptDomains(cls):
        return [cls.getSiteDomain(),'www.' + cls.getSiteDomain()]

    @classmethod
    def getSiteExampleURLs(cls):
        return cls.getViewStoryUrl('1234') + ' ' + cls.getViewStoryUrl('1234') + '&chapter=2'

    @classmethod
    def getSiteURLPattern(self):
        return r"http://(www\.)?%s%s/%s\?sid=(?P<storyId>\d+)" % (self.getSiteDomain(), self.getPathToArchive(), self.getViewStoryPhpName())

    @classmethod
    def getEncoding(cls):
        """
        Return an array of character encodings to try to decode the HTML with
        """
        return ["Windows-1252", "utf8"]


    @classmethod
    def getPathToArchive(cls):
        """
        Get the path segment of the archive, default '/'.

        In many cases, it's '/archive' or '/fanfiction'
        """
        return "/"

    @classmethod
    def getViewStoryPhpName(cls):
        """
        Get the name of the story PHP script, by default 'viewstory.php'
        """
        return "viewstory.php"

    @classmethod
    def getViewUserPhpName(cls):
        """
        Get the name of the user PHP script, by default 'viewuser.php'
        """
        return "viewuser.php"

    @classmethod
    def getUserPhpName(cls):
        """
        Get the name of the user PHP script, by default 'viewuser.php'
        """
        return "user.php"

    @classmethod
    def getDateFormat(self):
        """
        Describe the date format of this site in terms of strftime
        See http://docs.python.org/library/datetime.html#strftime-strptime-behavior
        """
        return "%d %b %Y"

    @classmethod
    def getUrlForPhp(self, php):
        return "http://%s%s/%s" % (self.getSiteDomain(), self.getPathToArchive(), php)

    @classmethod
    def getViewStoryUrl(self, storyId):
        """
        Get the URL to a user page on this site.
        """
        return "%s?sid=%s" % (self.getUrlForPhp(self.getViewStoryPhpName()), storyId)

    @classmethod
    def getViewUserUrl(self, userId):
        """
        Get the URL to a user page on this site.
        """
        return "%s?sid=%s" % (self.getUrlForPhp(self.getViewUserPhpName()), userId)

    @classmethod
    def getLoginUrl(self):
        """
        Get the URL to the login page on this site.
        """
        return "%s?action=login" % self.getUrlForPhp(self.getUserPhpName())

    @classmethod
    def getMessageRegisteredUsersOnly(self):
        """
        Constant _RUSERSONLY defined in languages/en.php
        """
        return _RUSERSONLY

    @classmethod
    def getMessageThereIsNoSuchAccount(self):
        """
        Constant _NOSUCHACCOUNT defined in languages/en.php
        """
        return _NOSUCHACCOUNT

    @classmethod
    def getMessageWrongPassword(self):
        """
        Constant _WRONGPASSWORD defined in languages/en.php
        """
        return _WRONGPASSWORD

    @classmethod
    def getMessageMemberAccount(self):
        """
        Constant _USERACCOUNT defined in languages/en.php
        """
        return _USERACCOUNT

    ## Login seems to be reasonably standard across eFiction sites.
    @classmethod
    def needToLoginCheck(self, html):
        """
        Return whether the HTML contains either of _RUSERSONLY, _NOSUCHACCOUNT or _WRONGPASSWORD
        """
        return getMessageRegisteredUsersOnly() in html \
                or getMessageThereIsNoSuchAccount in html \
                or getMessageWrongPassword in html

    def _fetch_to_soup(self, url):
        """
        Fetch a HTML document, fix it and parse it to BeautifulSoup.

        Replaces old characters, broken meta-tags, non-self-closing hr/br.

        Makes image links absolute so they can be downloaded
        """
        try:
            html = self._fetchUrl(url)
        except urllib2.HTTPError, e:
            if e.code == 404:
                raise exceptions.StoryDoesNotExist(self.url)
            else:
                raise e

        # Some site use old, old-school Comments <!- comment -> (single dash)
        html = re.sub("<!-.+?->", "", html)

        # There is a problem with meta tags on some sites where spaces aren't
        # properly encoded
        html = re.sub("<meta[^<>]+>(.*</meta>)?", "", html)

        # fix non-closing hr/br
        html = html.replace("<hr>", "<hr/>")
        html = html.replace("<br>", "<br/>")

        soup =  bs.BeautifulSoup(html, selfClosingTags=['br','hr']) # otherwise soup eats the br/hr tags.)

        ## fix all local image 'src' to absolute
        for img in soup.findAll("img", {"src": _REGEX_DOESNT_START_WITH_HTTP}):
            # TODO handle '../../' and so on
            if img['src'].startswith('/'):
                img['src'] = img['src'][1:]
            img['src'] = "http://%s%s/%s" % (self.getSiteDomain(), self.getPathToArchive(), img['src'])

        return soup

    def performLogin(self, url):
        params = {}

        if self.password:
            params['penname'] = self.username
            params['password'] = self.password
        else:
            params['penname'] = self.getConfig("username")
            params['password'] = self.getConfig("password")
        params['cookiecheck'] = '1'
        params['submit'] = 'Submit'

        logger.debug("Will now login to URL (%s) as (%s)" % (self.getLoginUrl(), params['penname']))

        d = self._fetchUrl(self.getLoginUrl(), params)

        if self.getMessageMemberAccount() not in d : #Member Account
            logger.info("Failed to login to URL <%s> as '%s'" % (self.getLoginUrl(), params['penname']))
            raise exceptions.FailedToLogin(url, params['penname'])
            return False
        else:
            return True

    def handleMetadataPair(self, key, value):
        """
        Handles a key-value pair of story metadata.

        Returns straight away if the value is 'None' (that's a string)

        Can be overridden by subclasses::
            def handleMetadataPair(self, key, value):
                if key == 'MyCustomKey':
                    self.story.setMetadata('somekye', value)
                else:
                    super(NameOfMyAdapter, self).handleMetadata(key, value)
        """
        # logger.debug("metadata: '%s' == '%s'" % (key, value))
        if value == 'None':
            return
        elif key == 'Summary':
            self.setDescription(self.url, value)
        elif 'Genre' in key:
            for val in re.split("\s*,\s*", value):
                self.story.addToList('genre', val)
        elif 'Warning' in key:
            for val in re.split("\s*,\s*", value):
                self.story.addToList('warnings', val)
        elif 'Characters' in key:
            for val in re.split("\s*,\s*", value):
                self.story.addToList('characters', val)
        elif 'Categories' in key:
            for val in re.split("\s*,\s*", value):
                self.story.addToList('categories', val)
        elif 'Challenges' in key:
            for val in re.split("\s*,\s*", value):
                # TODO this should be an official field I guess
                self.story.addToList('challenge', val)
        elif key == 'Chapters':
            self.story.setMetadata('numChapters', int(value))
        elif key == 'Rating':
            self.story.setMetadata('rating', value)
        elif key == 'Word count':
            self.story.setMetadata('numWords', value)
        elif key == 'Completed':
            if 'Yes' in value:
                self.story.setMetadata('status', 'Completed')
            else:
                self.story.setMetadata('status', 'In-Progress')
        elif key == 'Read':
            # TODO this should be an official field I guess
            self.story.setMetadata('readings', value)
        elif key == 'Published':
            self.story.setMetadata('datePublished', makeDate(value, self.getDateFormat()))
        elif key == 'Updated':
            self.story.setMetadata('dateUpdated', makeDate(value, self.getDateFormat()))
        elif key == 'Pairing':
            for val in re.split("\s*,\s*", value):
                self.story.addToList('ships', val)
        elif key == 'Series':
            ## TODO is not a link in the printable view, so no seriesURL possible 
            self.story.setMetadata('series', value)
        else:
            logger.info("Unhandled metadata pair: '%s' : '%s'" % (key, value))

    def extractChapterUrlsAndMetadata(self):
        printUrl = self.url + '&action=printable&textsize=0&chapter='
        if self.getConfig('bulk_load'):
            printUrl += 'all'
        else:
            printUrl += '1'


        soup = self._fetch_to_soup(printUrl)

        ## Handle warnings and login checks
        errorDiv = soup.find("div", "errortext")
        while errorDiv is not None:
            if self.getMessageRegisteredUsersOnly() in errorDiv.prettify():
                if not self.triedLoggingIn:
                    self.performLogin(self.url)
                    soup = self._fetch_to_soup(printUrl)
                    errorDiv = soup.find("div", "errortext")
                    self.triedLoggingIn = True
                else:
                    raise exceptions.FailedToLogin(self.url, str(errorDiv))
            else:
                warningLink = errorDiv.find("a")
                if warningLink is not None and ( \
                        'ageconsent' in warningLink['href'] \
                        or 'warning' in warningLink['href']):
                    if not self.triedAcceptWarnings:
                        if not (self.is_adult or self.getConfig("is_adult")):
                            raise exceptions.AdultCheckRequired(self.url)
                        # XXX Using this method, we're independent of # getHighestWarningLevel
                        printUrl += "&ageconsent=ok&warning=%s" % (_REGEX_WARING_PARAM.search(warningLink['href']).group(1))
                        # printUrl += "&ageconsent=ok&warning=%s" % self.getHighestWarningLevel()
                        soup = self._fetch_to_soup(printUrl)
                        errorDiv = soup.find("div", "errortext")
                        self.triedAcceptWarnings = True
                    else:
                        raise exception.FailedToDownload(self.url, str(errorDiv))
                else:
                    raise exception.FailedToDownload(self.url, str(errorDiv))

        # title and author
        pagetitleDiv = soup.find("div", {"id": "pagetitle"})
        if pagetitleDiv.find('a') is None:
            raise execeptions.FailedToDownload("Couldn't find title and author")
        self.story.setMetadata('title', pagetitleDiv.find("a").text)
        authorLink = pagetitleDiv.findAll("a")[1]
        self.story.setMetadata('author', authorLink.text)
        self.story.setMetadata('authorId', re.search("\d+", authorLink['href']).group(0))
        self.story.setMetadata('authorUrl', self.getViewUserUrl(self.story.getMetadata('authorId')))

        ## Parse the infobox
        labelSpans = soup.find("div", "infobox").find("div", "content").findAll("span", "label")
        for labelSpan in labelSpans:
            valueStr = ""
            nextEl = labelSpan.nextSibling
            while nextEl is not None and not (\
                        type(nextEl) is bs.Tag \
                        and nextEl.name == "span" \
                        and nextEl['class'] =='label' \
                        ):
                ## must string copy nextEl or nextEl will change trees
                if (type(nextEl) is bs.Tag):
                    valueStr += nextEl.prettify()
                else:
                    valueStr += str(nextEl)
                nextEl = nextEl.nextSibling
            key = labelSpan.text.strip()

            ## strip trailing line breaks
            valueStr = re.sub("<br />", "", valueStr)

            ## strip trailing colons
            key = re.sub("\s*:\s*$", "", key)

            ## strip whitespace
            key = key.strip()
            valueStr = valueStr.strip()

            self.handleMetadataPair(key, valueStr)

        ## Chapter URLs 

        # If we didn't bulk-load the whole chapter we now need to load
        # the non-printable HTML version of the landing page (i.e. the story
        # URL to get the Chapter titles
        if not self.getConfig('bulk_load'):
            soup = self._fetch_to_soup(self.url + '&index=1')

        chapterLinks = []
        for b in soup.findAll("b", text=_REGEX_CHAPTER_B):
            chapterId = _REGEX_CHAPTER_B.search(b).group('chapterId')
            chapterLink = b.findNext("a")
            chapterLink['href'] = "%s&chapter=%s" % (self.url, chapterId)
            self.chapterUrls.append((chapterLink.text, chapterLink['href']))

        ## Store reference to soup for getChapterText
        self.html = soup

    def getChapterText(self, url):
        if self.getConfig('bulk_load'):
            logger.debug('Cached chapter text from <%s>' % url)
            anchor = _REGEX_CHAPTER_PARAM.search(url).group(1)
            chapterDiv = self.html.find("a", {"name": anchor}).parent.findNext("div", "chapter")
        else:
            logger.debug('Download chapter text from <%s>' % url)
            soup = self._fetch_to_soup(url + '&action=printable')
            chapterDiv = soup.find("div", "chapter")
        return self.utf8FromSoup(self.url, chapterDiv)

def getClass():
    return BaseEfictionAdapter
