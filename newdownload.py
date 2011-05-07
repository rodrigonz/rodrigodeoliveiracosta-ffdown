# -*- coding: utf-8 -*-

import logging
logging.basicConfig(level=logging.DEBUG,format="%(levelname)s:%(filename)s(%(lineno)d):%(message)s")

import sys, os
from optparse import OptionParser      
import getpass

from fanficdownloader import adapters,writers,exceptions

import ConfigParser

def writeStory(config,adapter,writeformat):
    writer = writers.getWriter(writeformat,config,adapter.getStory())
    writer.writeStory()
    del writer

def main():
       
   # read in args, anything starting with -- will be treated as --<varible>=<value>
   usage = "usage: %prog [options] storyurl"
   parser = OptionParser(usage)
   parser.add_option("-f", "--format", dest="format", default='epub',
                     help="write story as FORMAT, epub(default), text or html", metavar="FORMAT")
   parser.add_option("-o", "--option",
                     action="append", dest="options",
                     help="set an option NAME=VALUE", metavar="NAME=VALUE")
   
   (options, args) = parser.parse_args()

   if len(args) != 1:
       parser.error("incorrect number of arguments")

   config = ConfigParser.SafeConfigParser()
   
   logging.debug('reading defaults.ini config file, if present')
   config.read('defaults.ini')
   logging.debug('reading personal.ini config file, if present')
   config.read('personal.ini')
   
   config.add_section("commandline")
   if options.options:
       for opt in options.options:
           (var,val) = opt.split('=')
           config.set("commandline",var,val)

   try:
       adapter = adapters.getAdapter(config,args[0])
           
       try:
           print adapter.getStoryMetadataOnly()
       except exceptions.FailedToLogin, ftl:
           print "Login Failed, Need Username/Password."
           sys.stdout.write("Username: ")
           adapter.username = sys.stdin.readline().strip()
           adapter.password = getpass.getpass(prompt='Password: ')
           #print("Login: `%s`, Password: `%s`" % (adapter.username, adapter.password))
           print adapter.getStoryMetadataOnly()


       ## XXX Use format.
       print "format: %s" % options.format
       writeStory(config,adapter,"epub")
       writeStory(config,adapter,"html")
       writeStory(config,adapter,"txt")
       del adapter
   
   except exceptions.InvalidStoryURL, isu:
       print isu
   except exceptions.StoryDoesNotExist, dne:
       print dne
   except exceptions.UnknownSite, us:
       print us
   
if __name__ == "__main__":
    main()
