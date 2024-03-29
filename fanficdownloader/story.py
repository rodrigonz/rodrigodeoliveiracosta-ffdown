# -*- coding: utf-8 -*-

# Copyright 2011 Fanficdownloader team
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

import os, re
import urlparse
import string
from math import floor
from functools import partial
import logging
logger = logging.getLogger(__name__)
import urlparse as up

import exceptions
from htmlcleanup import conditionalRemoveEntities, removeAllEntities
from configurable import Configurable

SPACE_REPLACE=u'\s'
SPLIT_META=u'\,'

# Create convert_image method depending on which graphics lib we can
# load.  Preferred: calibre, PIL, none

imagetypes = {
    'jpg':'image/jpeg',
    'jpeg':'image/jpeg',
    'png':'image/png',
    'gif':'image/gif',
    'svg':'image/svg+xml',
    }

try:
    from calibre.utils.magick import Image
    convtype = {'jpg':'JPG', 'png':'PNG'}

    def convert_image(url,data,sizes,grayscale,
                      removetrans,imgtype="jpg",background='#ffffff'):
        export = False
        img = Image()
        img.load(data)

        owidth, oheight = img.size
        nwidth, nheight = sizes
        scaled, nwidth, nheight = fit_image(owidth, oheight, nwidth, nheight)
        if scaled:
            img.size = (nwidth, nheight)
            export = True

        if normalize_format_name(img.format) != imgtype:
            export = True

        if removetrans and img.has_transparent_pixels():
            canvas = Image()
            canvas.create_canvas(int(img.size[0]), int(img.size[1]), str(background))
            canvas.compose(img)
            img = canvas
            export = True

        if grayscale and img.type != "GrayscaleType":
            img.type = "GrayscaleType"
            export = True

        if export:
            return (img.export(convtype[imgtype]),imgtype,imagetypes[imgtype])
        else:
            logger.debug("image used unchanged")
            return (data,imgtype,imagetypes[imgtype])

except:

    # No calibre routines, try for PIL for CLI.
    try:
        import Image
        from StringIO import StringIO
        convtype = {'jpg':'JPEG', 'png':'PNG'}
        def convert_image(url,data,sizes,grayscale,
                          removetrans,imgtype="jpg",background='#ffffff'):
            export = False
            img = Image.open(StringIO(data))

            owidth, oheight = img.size
            nwidth, nheight = sizes
            scaled, nwidth, nheight = fit_image(owidth, oheight, nwidth, nheight)
            if scaled:
                img = img.resize((nwidth, nheight),Image.ANTIALIAS)
                export = True

            if normalize_format_name(img.format) != imgtype:
                if img.mode == "P":
                    # convert pallete gifs to RGB so jpg save doesn't fail.
                    img = img.convert("RGB")
                export = True

            if removetrans and img.mode == "RGBA":
                background = Image.new('RGBA', img.size, background)
                # Paste the image on top of the background
                background.paste(img, img)
                img = background.convert('RGB')
                export = True

            if grayscale and img.mode != "L":
                img = img.convert("L")
                export = True

            if export:
                outsio = StringIO()
                img.save(outsio,convtype[imgtype])
                return (outsio.getvalue(),imgtype,imagetypes[imgtype])
            else:
                logger.debug("image used unchanged")
                return (data,imgtype,imagetypes[imgtype])

    except:
        # No calibre or PIL, simple pass through with mimetype.
        def convert_image(url,data,sizes,grayscale,
                          removetrans,imgtype="jpg",background='#ffffff'):
            return no_convert_image(url,data)

## also used for explicit no image processing.
def no_convert_image(url,data):
    parsedUrl = up.urlparse(url)

    ext=parsedUrl.path[parsedUrl.path.rfind('.')+1:].lower()

    if ext not in imagetypes:
        logger.debug("no_convert_image url:%s - no known extension"%url)
        # doesn't have extension? use jpg.
        ext='jpg'

    return (data,ext,imagetypes[ext])

def normalize_format_name(fmt):
    if fmt:
        fmt = fmt.lower()
        if fmt == 'jpeg':
            fmt = 'jpg'
    return fmt

def fit_image(width, height, pwidth, pheight):
    '''
    Fit image in box of width pwidth and height pheight.
    @param width: Width of image
    @param height: Height of image
    @param pwidth: Width of box
    @param pheight: Height of box
    @return: scaled, new_width, new_height. scaled is True iff new_width and/or new_height is different from width or height.
    '''
    scaled = height > pheight or width > pwidth
    if height > pheight:
        corrf = pheight/float(height)
        width, height = floor(corrf*width), pheight
    if width > pwidth:
        corrf = pwidth/float(width)
        width, height = pwidth, floor(corrf*height)
    if height > pheight:
        corrf = pheight/float(height)
        width, height = floor(corrf*width), pheight

    return scaled, int(width), int(height)

try:
    # doesn't really matter what, just checking for appengine.
    from google.appengine.api import apiproxy_stub_map

    is_appengine = True
except:
    is_appengine = False


# The list comes from ffnet, the only multi-language site we support
# at the time of writing.  Values are taken largely from pycountry,
# but with some corrections and guesses.
langs = {
    "English":"en",
    "Spanish":"es",
    "French":"fr",
    "German":"de",
    "Chinese":"zh",
    "Japanese":"ja",
    "Dutch":"nl",
    "Portuguese":"pt",
    "Russian":"ru",
    "Italian":"it",
    "Bulgarian":"bg",
    "Polish":"pl",
    "Hungarian":"hu",
    "Hebrew":"he",
    "Arabic":"ar",
    "Swedish":"sv",
    "Norwegian":"no",
    "Danish":"da",
    "Finnish":"fi",
    "Filipino":"fil",
    "Esperanto":"eo",
    "Hindi":"hi",
    "Punjabi":"pa",
    "Farsi":"fa",
    "Greek":"el",
    "Romanian":"ro",
    "Albanian":"sq",
    "Serbian":"sr",
    "Turkish":"tr",
    "Czech":"cs",
    "Indonesian":"id",
    "Croatian":"hr",
    "Catalan":"ca",
    "Latin":"la",
    "Korean":"ko",
    "Vietnamese":"vi",
    "Thai":"th",
    "Devanagari":"hi",
    }

class InExMatch:
    keys = []
    regex = None
    match = None
    negate = False

    def  __init__(self,line):
        if "=~" in line:
            (self.keys,self.match) = line.split("=~")
            self.match = self.match.replace(SPACE_REPLACE,' ')
            self.regex = re.compile(self.match)
        elif "!~" in line:
            (self.keys,self.match) = line.split("!~")
            self.match = self.match.replace(SPACE_REPLACE,' ')
            self.regex = re.compile(self.match)
            self.negate = True
        elif "==" in line:
            (self.keys,self.match) = line.split("==")
            self.match = self.match.replace(SPACE_REPLACE,' ')
        elif "!=" in line:
            (self.keys,self.match) = line.split("!=")
            self.match = self.match.replace(SPACE_REPLACE,' ')
            self.negate = True
        self.keys = map( lambda x: x.strip(), self.keys.split(",") )

    # For conditional, only one key
    def is_key(self,key):
        return key == self.keys[0]

    # For conditional, only one key
    def key(self):
        return self.keys[0]

    def in_keys(self,key):
        return key in self.keys

    def is_match(self,value):
        retval = False
        if self.regex:
            if self.regex.search(value):
                retval = True
            #print(">>>>>>>>>>>>>%s=~%s r: %s,%s=%s"%(self.match,value,self.negate,retval,self.negate != retval))
        else:
            retval = self.match == value
            #print(">>>>>>>>>>>>>%s==%s r: %s,%s=%s"%(self.match,value,self.negate,retval, self.negate != retval))
            
        return self.negate != retval

    def __str__(self):
        if self.negate:
            f='!'
        else:
            f='='
        if self.regex:
            s='~'
        else:
            s='='
        return u'InExMatch(%s %s%s %s)'%(self.keys,f,s,self.match)

class Story(Configurable):

    def __init__(self, configuration):
        Configurable.__init__(self, configuration)
        try:
            ## calibre plugin will set externally to match PI version.
            self.metadata = {'version':os.environ['CURRENT_VERSION_ID']}
        except:
            self.metadata = {'version':'4.4'}
        self.replacements = []
        self.in_ex_cludes = {}
        self.chapters = [] # chapters will be tuples of (title,html)
        self.imgurls = []
        self.imgtuples = []

        self.cover=None # *href* of new cover image--need to create html.
        self.oldcover=None # (oldcoverhtmlhref,oldcoverhtmltype,oldcoverhtmldata,oldcoverimghref,oldcoverimgtype,oldcoverimgdata)
        self.calibrebookmark=None # cheesy way to carry calibre bookmark file forward across update.
        self.logfile=None # cheesy way to carry log file forward across update.

        ## Look for config parameter, split and add each to metadata field.
        for (config,metadata) in [("extracategories","category"),
                                  ("extragenres","genre"),
                                  ("extracharacters","characters"),
                                  ("extraships","ships"),
                                  ("extrawarnings","warnings")]:
            for val in self.getConfigList(config):
                self.addToList(metadata,val)

        self.setReplace(self.getConfig('replace_metadata'))

        in_ex_clude_list = ['include_metadata_pre','exclude_metadata_pre',
                            'include_metadata_post','exclude_metadata_post']
        for ie in in_ex_clude_list:
            ies = self.getConfig(ie)
            # print("%s %s"%(ie,ies))
            if ies:
                iel = []
                self.in_ex_cludes[ie] = self.set_in_ex_clude(ies)

    def join_list(self, key, vallist):
        return self.getConfig("join_string_"+key,u", ").replace(SPACE_REPLACE,' ').join(map(unicode, vallist))
                
    def setMetadata(self, key, value, condremoveentities=True):

        # keep as list type, but set as only value.
        if self.isList(key):
            self.addToList(key,value,condremoveentities=condremoveentities,clear=True)
        else:
            ## still keeps &lt; &lt; and &amp;
            if condremoveentities:
                self.metadata[key]=conditionalRemoveEntities(value)
            else:
                self.metadata[key]=value
                
        if key == "language":
            try:
                # getMetadata not just self.metadata[] to do replace_metadata.
                self.setMetadata('langcode',langs[self.getMetadata(key)])
            except:
                self.setMetadata('langcode','en')
                
        if key == 'dateUpdated' and value:
            # Last Update tags for Bill.
            self.addToList('lastupdate',value.strftime("Last Update Year/Month: %Y/%m"))
            self.addToList('lastupdate',value.strftime("Last Update: %Y/%m/%d"))

        
    ## metakey[,metakey]=~pattern
    ## metakey[,metakey]==string
    ## *for* part lines.  Effect only when trailing conditional key=~regexp matches
    ## metakey[,metakey]=~pattern[&&metakey=~regexp]
    ## metakey[,metakey]==string[&&metakey=~regexp]
    ## metakey[,metakey]=~pattern[&&metakey==string]
    ## metakey[,metakey]==string[&&metakey==string]
    def set_in_ex_clude(self,setting):
        dest = []
        # print("set_in_ex_clude:"+setting)
        for line in setting.splitlines():
            if line:
                (match,condmatch)=(None,None)
                if "&&" in line:
                    (line,conditional) = line.split("&&")
                    condmatch = InExMatch(conditional)
                match = InExMatch(line)
                dest.append([match,condmatch])
        return dest
              
    def do_in_ex_clude(self,which,value,key):
        if value and which in self.in_ex_cludes:
            include = 'include' in which
            keyfound = False
            found = False
            for (match,condmatch) in self.in_ex_cludes[which]:
                keyfndnow = False
                if match.in_keys(key):
                    # key in keys and either no conditional, or conditional matched
                    if condmatch == None or condmatch.is_key(key):
                        keyfndnow = True
                    else:
                        condval = self.getMetadata(condmatch.key())
                        keyfndnow = condmatch.is_match(condval)
                    keyfound |= keyfndnow
                        # print("match:%s %s\ncondmatch:%s %s\n\tkeyfound:%s\n\tfound:%s"%(
                        #         match,value,condmatch,condval,keyfound,found))
                    if keyfndnow:
                        found = isinstance(value,basestring) and match.is_match(value)
                    if found:
                        # print("match:%s %s\n\tkeyfndnow:%s\n\tfound:%s"%(
                        #         match,value,keyfndnow,found))
                        if not include:
                            value = None
                        break
            if include and keyfound and not found:
                value = None
        return value
        

    ## Two or three part lines.  Two part effect everything.
    ## Three part effect only those key(s) lists.
    ## pattern=>replacement
    ## metakey,metakey=>pattern=>replacement
    ## *Five* part lines.  Effect only when trailing conditional key=>regexp matches
    ## metakey[,metakey]=>pattern=>replacement[&&metakey=>regexp]
    def setReplace(self,replace):
        for line in replace.splitlines():
            # print("replacement line:%s"%line)
            (metakeys,regexp,replacement,condkey,condregexp)=(None,None,None,None,None)
            if "&&" in line:
                (line,conditional) = line.split("&&")
                (condkey,condregexp) = conditional.split("=>")
            if "=>" in line:
                parts = line.split("=>")
                if len(parts) > 2:
                    metakeys = map( lambda x: x.strip(), parts[0].split(",") )
                    (regexp,replacement)=parts[1:]
                else:
                    (regexp,replacement)=parts

            if regexp:
                regexp = re.compile(regexp)
                if condregexp:
                    condregexp = re.compile(condregexp)
                # A way to explicitly include spaces in the
                # replacement string.  The .ini parser eats any
                # trailing spaces.
                replacement=replacement.replace(SPACE_REPLACE,' ')
                self.replacements.append([metakeys,regexp,replacement,condkey,condregexp])

    def doReplacements(self,value,key,return_list=False,seen_list=[]):
        value = self.do_in_ex_clude('include_metadata_pre',value,key)
        value = self.do_in_ex_clude('exclude_metadata_pre',value,key)

        retlist = [value]
        for replaceline in self.replacements:
            if replaceline in seen_list: # recursion on pattern, bail
                # print("bailing on %s"%replaceline)
                continue
            #print("replacement tuple:%s"%replaceline)
            (metakeys,regexp,replacement,condkey,condregexp) = replaceline
            if (metakeys == None or key in metakeys) \
                    and isinstance(value,basestring) \
                    and regexp.search(value):
                doreplace=True
                if condkey and condkey != key: # prevent infinite recursion.
                    condval = self.getMetadata(condkey)
                    doreplace = condval != None and condregexp.search(condval)

                if doreplace:
                    # split into more than one list entry if
                    # SPLIT_META present in replacement string.  Split
                    # first, then regex sub, then recurse call replace
                    # on each.  Break out of loop, each split element
                    # handled individually by recursion call.
                    if SPLIT_META in replacement:
                        retlist = []
                        for splitrepl in replacement.split(SPLIT_META):
                            retlist.extend(self.doReplacements(regexp.sub(splitrepl,value),
                                                               key,
                                                               return_list=True,
                                                               seen_list=seen_list+[replaceline]))
                        break
                    else:
                        # print("replacement,value:%s,%s->%s"%(replacement,value,regexp.sub(replacement,value)))
                        value = regexp.sub(replacement,value)
                        retlist = [value]
                    
        for val in retlist:
            retlist = map(partial(self.do_in_ex_clude,'include_metadata_post',key=key),retlist)
            retlist = map(partial(self.do_in_ex_clude,'exclude_metadata_post',key=key),retlist)
        # value = self.do_in_ex_clude('include_metadata_post',value,key)
        # value = self.do_in_ex_clude('exclude_metadata_post',value,key)

        if return_list:
            return retlist
        else:
            return self.join_list(key,retlist)

    def getMetadataRaw(self,key):
        if self.isValidMetaEntry(key) and self.metadata.has_key(key):
            return self.metadata[key]

    def getMetadata(self, key,
                    removeallentities=False,
                    doreplacements=True):
        value = None
        if not self.isValidMetaEntry(key):
            return value

        if self.isList(key):
            # join_string = self.getConfig("join_string_"+key,u", ").replace(SPACE_REPLACE,' ')
            # value = join_string.join(self.getList(key, removeallentities, doreplacements=True))
            value = self.join_list(key,self.getList(key, removeallentities, doreplacements=True))
            if doreplacements:
                value = self.doReplacements(value,key+"_LIST")
            return value
        elif self.metadata.has_key(key):
            value = self.metadata[key]
            if value:
                if key == "numWords":
                    value = commaGroups(value)
                if key == "numChapters":
                    value = commaGroups("%d"%value)
                if key in ("dateCreated"):
                    value = value.strftime(self.getConfig(key+"_format","%Y-%m-%d %H:%M:%S"))
                if key in ("datePublished","dateUpdated"):
                    value = value.strftime(self.getConfig(key+"_format","%Y-%m-%d"))

            if doreplacements:
                value=self.doReplacements(value,key)
            if removeallentities and value != None:
                return removeAllEntities(value)
            else:
                return value
        else: #if self.getConfig("default_value_"+key):
            return self.getConfig("default_value_"+key)

    def getAllMetadata(self,
                       removeallentities=False,
                       doreplacements=True,
                       keeplists=False):
        '''
        All single value *and* list value metadata as strings (unless
        keeplists=True, then keep lists).
        '''
        allmetadata = {}

        # special handling for authors/authorUrls
        linkhtml="<a class='%slink' href='%s'>%s</a>"
        if self.isList('author'): # more than one author, assume multiple authorUrl too.
            htmllist=[]
            for i, v in enumerate(self.getList('author')):
                aurl = self.getList('authorUrl')[i]
                auth = v
                # make sure doreplacements & removeallentities are honored.
                if doreplacements:
                    aurl=self.doReplacements(aurl,'authorUrl')
                    auth=self.doReplacements(auth,'author')
                if removeallentities:
                    aurl=removeAllEntities(aurl)
                    auth=removeAllEntities(auth)

                htmllist.append(linkhtml%('author',aurl,auth))
            # join_string = self.getConfig("join_string_authorHTML",u", ").replace(SPACE_REPLACE,' ')
            self.setMetadata('authorHTML',self.join_list("join_string_authorHTML",htmllist))
        else:
            self.setMetadata('authorHTML',linkhtml%('author',self.getMetadata('authorUrl', removeallentities, doreplacements),
                                                    self.getMetadata('author', removeallentities, doreplacements)))

        if self.getMetadataRaw('seriesUrl'):
            self.setMetadata('seriesHTML',linkhtml%('series',self.getMetadata('seriesUrl', removeallentities, doreplacements),
                                                    self.getMetadata('series', removeallentities, doreplacements)))
        elif self.getMetadataRaw('series'):
            self.setMetadata('seriesHTML',self.getMetadataRaw('series'))

        # logger.debug("make_linkhtml_entries:%s"%self.getConfig('make_linkhtml_entries'))
        for k in self.getConfigList('make_linkhtml_entries'):
            # Assuming list, because it has to be site specific and
            # they are all lists.  Bail if kUrl list not the same
            # length.
            # logger.debug("\nk:%s\nlist:%s\nlistURL:%s"%(k,self.getList(k),self.getList(k+'Url')))
            if len(self.getList(k+'Url')) != len(self.getList(k)):
                continue
            htmllist=[]
            for i, v in enumerate(self.getList(k)):
                url = self.getList(k+'Url')[i]
                # make sure doreplacements & removeallentities are honored.
                if doreplacements:
                    url=self.doReplacements(url,k+'Url')
                    v=self.doReplacements(v,k)
                if removeallentities:
                    url=removeAllEntities(url)
                    v=removeAllEntities(v)

                htmllist.append(linkhtml%(k,url,v))
            # join_string = self.getConfig("join_string_"+k+"HTML",u", ").replace(SPACE_REPLACE,' ')
            self.setMetadata(k+'HTML',self.join_list("join_string_"+k+"HTML",htmllist))

        for k in self.getValidMetaList():
            if self.isList(k) and keeplists:
                allmetadata[k] = self.getList(k, removeallentities, doreplacements)
            else:
                allmetadata[k] = self.getMetadata(k, removeallentities, doreplacements)

        return allmetadata

    # just for less clutter in adapters.
    def extendList(self,listname,l):
        for v in l:
            self.addToList(listname,v.strip())

    def addToList(self,listname,value,condremoveentities=True,clear=False):
        if value==None:
            return
        if condremoveentities:
            value = conditionalRemoveEntities(value)
        if clear or not self.isList(listname) or not listname in self.metadata:
            # Calling addToList to a non-list meta will overwrite it.
            self.metadata[listname]=[]
        # prevent duplicates.
        if not value in self.metadata[listname]:
            self.metadata[listname].append(value)

        if listname == 'category' and self.getConfig('add_genre_when_multi_category') and len(self.metadata[listname]) > 1:
            self.addToList('genre',self.getConfig('add_genre_when_multi_category'))

    def isList(self,listname):
        'Everything set with an include_in_* is considered a list.'
        return self.isListType(listname) or \
            ( self.isValidMetaEntry(listname) and self.metadata.has_key(listname) \
                  and isinstance(self.metadata[listname],list) )

    def getList(self,listname,
                removeallentities=False,
                doreplacements=True,
                includelist=[]):
        #print("getList(%s,%s)"%(listname,includelist))
        retlist = []

        if not self.isValidMetaEntry(listname):
            return retlist

        # includelist prevents infinite recursion of include_in_'s
        if self.hasConfig("include_in_"+listname) and listname not in includelist:
            for k in self.getConfigList("include_in_"+listname):
                retlist.extend(self.getList(k,removeallentities=False,
                                            doreplacements=doreplacements,includelist=includelist+[listname]))
        else:

            if not self.isList(listname):
                retlist = [self.getMetadata(listname,removeallentities=False,
                                            doreplacements=doreplacements)]
            else:
                retlist = self.getMetadataRaw(listname)

        if retlist:
            if doreplacements:
                newretlist = []
                for val in retlist:
                    newretlist.extend(self.doReplacements(val,listname,return_list=True))
                retlist = newretlist
                
            if removeallentities:
                retlist = map(removeAllEntities,retlist)
                
            retlist = filter( lambda x : x!=None and x!='' ,retlist)

        # reorder ships so b/a and c/b/a become a/b and a/b/c.  Only on '/',
        # use replace_metadata to change separator first if needed.
        # ships=>[ ]*(/|&amp;|&)[ ]*=>/
        if listname == 'ships' and self.getConfig('sort_ships') and retlist:
            retlist = [ '/'.join(sorted(x.split('/'))) for x in retlist ]

        if retlist:
            if listname in ('author','authorUrl','authorId') or self.getConfig('keep_in_order_'+listname):
                # need to retain order for author & authorUrl so the
                # two match up.
                return retlist
            else:
                # remove dups and sort.
                return sorted(list(set(retlist)))
        else:
            return []

    def getSubjectTags(self, removeallentities=False):
        # set to avoid duplicates subject tags.
        subjectset = set()

        tags_list = self.getConfigList("include_subject_tags") + self.getConfigList("extra_subject_tags")

        # metadata all go into dc:subject tags, but only if they are configured.
        for (name,value) in self.getAllMetadata(removeallentities=removeallentities,keeplists=True).iteritems():
            if name in tags_list:
                if isinstance(value,list):
                    for tag in value:
                        subjectset.add(tag)
                else:
                    subjectset.add(value)

        if None in subjectset:
            subjectset.remove(None)
        if '' in subjectset:
            subjectset.remove('')

        return list(subjectset | set(self.getConfigList("extratags")))

    def addChapter(self, url, title, html):
        if self.getConfig('strip_chapter_numbers') and \
                self.getConfig('chapter_title_strip_pattern'):
            title = re.sub(self.getConfig('chapter_title_strip_pattern'),"",title)
        self.chapters.append( (url,title,html) )

    def getChapters(self,fortoc=False):
        "Chapters will be tuples of (title,html)"
        retval = []
        ## only add numbers if more than one chapter.
        if len(self.chapters) > 1 and \
                (self.getConfig('add_chapter_numbers') == "true" \
                     or (self.getConfig('add_chapter_numbers') == "toconly" and fortoc)) \
                     and self.getConfig('chapter_title_add_pattern'):
            for index, (url,title,html) in enumerate(self.chapters):
                retval.append( (url,
                                string.Template(self.getConfig('chapter_title_add_pattern')).substitute({'index':index+1,'title':title}),
                                html) )
        else:
            retval = self.chapters

        return retval

    def formatFileName(self,template,allowunsafefilename=True):
        values = origvalues = self.getAllMetadata()
        # fall back default:
        if not template:
            template="${title}-${siteabbrev}_${storyId}${formatext}"

        if not allowunsafefilename:
            values={}
            pattern = re.compile(self.getConfig("output_filename_safepattern",r"[^a-zA-Z0-9_\. \[\]\(\)&'-]+"))
            for k in origvalues.keys():
                values[k]=re.sub(pattern,'_', removeAllEntities(self.getMetadata(k)))

        return string.Template(template).substitute(values).encode('utf8')

    # pass fetch in from adapter in case we need the cookies collected
    # as well as it's a base_story class method.
    def addImgUrl(self,parenturl,url,fetch,cover=False,coverexclusion=None):

        # otherwise it saves the image in the epub even though it
        # isn't used anywhere.
        if cover and self.getConfig('never_make_cover'):
            return

        url = url.strip() # ran across an image with a space in the
                          # src. Browser handled it, so we'd better, too.

        # appengine (web version) isn't allowed to do images--just
        # gets too big too fast and breaks things.
        if is_appengine:
            return

        if url.startswith("http") or url.startswith("file") or parenturl == None:
            imgurl = url
        else:
            parsedUrl = urlparse.urlparse(parenturl)
            if url.startswith("//") :
                imgurl = urlparse.urlunparse(
                    (parsedUrl.scheme,
                     '',
                     url,
                     '','',''))
            elif url.startswith("/") :
                imgurl = urlparse.urlunparse(
                    (parsedUrl.scheme,
                     parsedUrl.netloc,
                     url,
                     '','',''))
            else:
                toppath=""
                if parsedUrl.path.endswith("/"):
                    toppath = parsedUrl.path
                else:
                    toppath = parsedUrl.path[:parsedUrl.path.rindex('/')]
                imgurl = urlparse.urlunparse(
                    (parsedUrl.scheme,
                     parsedUrl.netloc,
                     toppath + '/' + url,
                     '','',''))
                #print("\n===========\nparsedUrl.path:%s\ntoppath:%s\nimgurl:%s\n\n"%(parsedUrl.path,toppath,imgurl))

        # apply coverexclusion to explicit covers, too.  Primarily for ffnet imageu.
        if cover and coverexclusion and re.search(coverexclusion,imgurl):
            return

        prefix='ffdl'
        if imgurl not in self.imgurls:
            parsedUrl = urlparse.urlparse(imgurl)

            try:
                if self.getConfig('no_image_processing'):
                    (data,ext,mime) = no_convert_image(imgurl,
                                                       fetch(imgurl))
                else:
                    try:
                        sizes = [ int(x) for x in self.getConfigList('image_max_size') ]
                    except Exception, e:
                        raise exceptions.FailedToDownload("Failed to parse image_max_size from personal.ini:%s\nException: %s"%(self.getConfigList('image_max_size'),e))
                    grayscale = self.getConfig('grayscale_images')
                    imgtype = self.getConfig('convert_images_to')
                    if not imgtype:
                        imgtype = "jpg"
                    removetrans = self.getConfig('remove_transparency')
                    removetrans = removetrans or grayscale or imgtype=="jpg"
                    (data,ext,mime) = convert_image(imgurl,
                                                    fetch(imgurl),
                                                    sizes,
                                                    grayscale,
                                                    removetrans,
                                                    imgtype,
                                                    background="#"+self.getConfig('background_color'))
            except Exception, e:
                logger.info("Failed to load or convert image, skipping:\n%s\nException: %s"%(imgurl,e))
                return "failedtoload"

            # explicit cover, make the first image.
            if cover:
                if len(self.imgtuples) > 0 and 'cover' in self.imgtuples[0]['newsrc']:
                    # remove existing cover, if there is one.
                    del self.imgurls[0]
                    del self.imgtuples[0]
                self.imgurls.insert(0,imgurl)
                newsrc = "images/cover.%s"%ext
                self.cover=newsrc
                self.imgtuples.insert(0,{'newsrc':newsrc,'mime':mime,'data':data})
            else:
                self.imgurls.append(imgurl)
                # First image, copy not link because calibre will replace with it's cover.
                # Only if: No cover already AND
                #          make_firstimage_cover AND
                #          NOT never_make_cover AND
                #          either no coverexclusion OR coverexclusion doesn't match
                if self.cover == None and \
                        self.getConfig('make_firstimage_cover') and \
                        not self.getConfig('never_make_cover') and \
                        not (coverexclusion and re.search(coverexclusion,imgurl)):
                    newsrc = "images/cover.%s"%ext
                    self.cover=newsrc
                    self.imgtuples.append({'newsrc':newsrc,'mime':mime,'data':data})
                    self.imgurls.append(imgurl)

                newsrc = "images/%s-%s.%s"%(
                    prefix,
                    self.imgurls.index(imgurl),
                    ext)
                self.imgtuples.append({'newsrc':newsrc,'mime':mime,'data':data})

            #logger.debug("\nimgurl:%s\nnewsrc:%s\nimage size:%d\n"%(imgurl,newsrc,len(data)))
        else:
            newsrc = self.imgtuples[self.imgurls.index(imgurl)]['newsrc']

        #print("===============\n%s\nimg url:%s\n============"%(newsrc,self.imgurls[-1]))

        return newsrc

    def getImgUrls(self):
        retlist = []
        for i, url in enumerate(self.imgurls):
            #parsedUrl = urlparse.urlparse(url)
            retlist.append(self.imgtuples[i])
        return retlist

    def __str__(self):
        return "Metadata: " +str(self.metadata)

def commaGroups(s):
    groups = []
    while s and s[-1].isdigit():
        groups.append(s[-3:])
        s = s[:-3]
    return s + ','.join(reversed(groups))

