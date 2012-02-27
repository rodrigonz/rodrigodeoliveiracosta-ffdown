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

import logging
## XXX cli option for logging level.
logging.basicConfig(level=logging.DEBUG,format="%(levelname)s:%(filename)s(%(lineno)d):%(message)s")

import sys, os
from os.path import normpath, expanduser, isfile, join
from StringIO import StringIO
from optparse import OptionParser      
import getpass
import string
import ConfigParser
from subprocess import call

from fanficdownloader import adapters,writers,exceptions
from fanficdownloader.epubutils import get_dcsource_chaptercount, get_update_data

if sys.version_info < (2, 5):
    print "This program requires Python 2.5 or newer."
    sys.exit(1)

def writeStory(config,adapter,writeformat,metaonly=False,outstream=None):
    writer = writers.getWriter(writeformat,config,adapter)
    writer.writeStory(outstream=outstream,metaonly=metaonly)
    output_filename=writer.getOutputFileName()
    del writer
    return output_filename

def main():
   # read in args, anything starting with -- will be treated as --<varible>=<value>
   usage = "usage: %prog [options] storyurl"
   parser = OptionParser(usage)
   parser.add_option("-f", "--format", dest="format", default="epub",
                     help="write story as FORMAT, epub(default), text or html", metavar="FORMAT")
   parser.add_option("-c", "--config",
                     action="append", dest="configfile", default=None,
                     help="read config from specified file(s) in addition to ~/.fanficdownloader/defaults.ini, ~/.fanficdownloader/personal.ini, ./defaults.ini, ./personal.ini", metavar="CONFIG")
   parser.add_option("-b", "--begin", dest="begin", default=None,
                     help="Begin with Chapter START", metavar="START")
   parser.add_option("-e", "--end", dest="end", default=None,
                     help="End with Chapter END", metavar="END")
   parser.add_option("-o", "--option",
                     action="append", dest="options",
                     help="set an option NAME=VALUE", metavar="NAME=VALUE")
   parser.add_option("-m", "--meta-only",
                     action="store_true", dest="metaonly",
                     help="Retrieve metadata and stop.  Or, if --update-epub, update metadata title page only.",)
   parser.add_option("-u", "--update-epub",
                     action="store_true", dest="update",
                     help="Update an existing epub with new chapter, give epub filename instead of storyurl.  Not compatible with inserted TOC.",)
   parser.add_option("--force",
                     action="store_true", dest="force",
                     help="Force overwrite or update of an existing epub, download and overwrite all chapters.",)
   
   (options, args) = parser.parse_args()

   if len(args) != 1:
       parser.error("incorrect number of arguments")

   if options.update and options.format != 'epub':
       parser.error("-u/--update-epub only works with epub")

   config = ConfigParser.SafeConfigParser()

   conflist = []
   homepath = join(expanduser("~"),".fanficdownloader")
   
   if isfile(join(homepath,"defaults.ini")):
       conflist.append(join(homepath,"defaults.ini"))
   if isfile("defaults.ini"):
       conflist.append("defaults.ini")
       
   if isfile(join(homepath,"personal.ini")):
       conflist.append(join(homepath,"personal.ini"))
   if isfile("personal.ini"):
       conflist.append("personal.ini")
       
   if options.configfile:
       conflist.extend(options.configfile)
      
   logging.debug('reading %s config file(s), if present'%conflist)
   config.read(conflist)

   try:
       config.add_section("overrides")
   except ConfigParser.DuplicateSectionError:
       pass

   if options.force:
       config.set("overrides","always_overwrite","true")
       
   if options.options:
       for opt in options.options:
           (var,val) = opt.split('=')
           config.set("overrides",var,val)

   try:
       ## Attempt to update an existing epub.
       if options.update:
           # updateio = StringIO()
           # (url,chaptercount) = doMerge(updateio,
           #                              args,
           #                              titlenavpoints=False,
           #                              striptitletoc=True,
           #                              forceunique=False)
           (url,chaptercount) = get_dcsource_chaptercount(args[0])
           print "Updating %s, URL: %s" % (args[0],url)
           output_filename = args[0]
           config.set("overrides","output_filename",args[0])
       else:
           url = args[0]

       adapter = adapters.getAdapter(config,url,options.format)

       ## Check for include_images and absence of PIL, give warning.
       if adapter.getConfig('include_images'):
           try:
               import Image
           except:
               print "You have include_images enabled, but Python Image Library(PIL) isn't found.\nImages will be included full size in original format.\nContinue? (y/n)?"
               if not sys.stdin.readline().strip().lower().startswith('y'):
                   return
               

       ## three tries, that's enough if both user/pass & is_adult needed,
       ## or a couple tries of one or the other
       for x in range(0,2):
           try:
               adapter.getStoryMetadataOnly()
           except exceptions.FailedToLogin:
               print "Login Failed, Need Username/Password."
               sys.stdout.write("Username: ")
               adapter.username = sys.stdin.readline().strip()
               adapter.password = getpass.getpass(prompt='Password: ')
               #print("Login: `%s`, Password: `%s`" % (adapter.username, adapter.password))
           except exceptions.AdultCheckRequired:
               print "Please confirm you are an adult in your locale: (y/n)?"
               if sys.stdin.readline().strip().lower().startswith('y'):
                   adapter.is_adult=True

       if options.update and not options.force:
           urlchaptercount = int(adapter.getStoryMetadataOnly().getMetadata('numChapters'))
           
           if chaptercount == urlchaptercount and not options.metaonly:
               print "%s already contains %d chapters." % (args[0],chaptercount)
           elif chaptercount > urlchaptercount:
               print "%s contains %d chapters, more than source: %d." % (args[0],chaptercount,urlchaptercount)
           else:
               print "Do update - epub(%d) vs url(%d)" % (chaptercount, urlchaptercount)
               ## Get updated title page/metadata by itself in an epub.
               ## Even if the title page isn't included, this carries the metadata.
               # titleio = StringIO()
               # writeStory(config,adapter,"epub",metaonly=True,outstream=titleio)

               # newchaptersio = None
               if not options.metaonly:
                   (url,chaptercount,
                    adapter.oldchapters,
                    adapter.oldimgs) = get_update_data(args[0])

                   writeStory(config,adapter,"epub")
                   
                   ## Go get the new chapters only in another epub.
                   # newchaptersio = StringIO()
                   # adapter.setChaptersRange(chaptercount+1,urlchaptercount)
                   # config.set("overrides",'include_tocpage','false')
                   # config.set("overrides",'include_titlepage','false')
                   # writeStory(config,adapter,"epub",outstream=newchaptersio)
               
               # out = open("testing/titleio.epub","wb")
               # out.write(titleio.getvalue())
               # out.close()
               
               # out = open("testing/updateio.epub","wb")
               # out.write(updateio.getvalue())
               # out.close()
               
               # out = open("testing/newchaptersio.epub","wb")
               # out.write(newchaptersio.getvalue())
               # out.close()
               
               ## Merge the three epubs together.
               # doMerge(args[0],
               #         [titleio,updateio,newchaptersio],
               #         fromfirst=True,
               #         titlenavpoints=False,
               #         striptitletoc=False,
               #         forceunique=False)

       else:
           # regular download
           if options.metaonly:
               print adapter.getStoryMetadataOnly()
           
           adapter.setChaptersRange(options.begin,options.end)
           
           output_filename=writeStory(config,adapter,options.format,options.metaonly)
       
       if not options.metaonly and adapter.getConfig("post_process_cmd"):
           metadata = adapter.story.metadata
           metadata['output_filename']=output_filename
           call(string.Template(adapter.getConfig("post_process_cmd"))
                .substitute(metadata), shell=True)
           
       del adapter
   
   except exceptions.InvalidStoryURL, isu:
       print isu
   except exceptions.StoryDoesNotExist, dne:
       print dne
   except exceptions.UnknownSite, us:
       print us
   
if __name__ == "__main__":
    #import time
    #start = time.time()
    main()
    #print("Total time seconds:%f"%(time.time()-start))
