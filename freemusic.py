#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Based on PirateApp by thisismyfakemail123 - http://code.google.com/p/pirateapp/
#

import re
import os
import sys
import urllib
import urllib2
import httplib2
from BeautifulSoup import BeautifulSoup

class LoginFailedException(Exception):
    pass

class SongParseError(Exception):
    pass

class Song:
    artist = None
    title = None
    duration = 0
    size = 0
    bitrate = 0
    url = None

    def __init__(self, url):
        self.url = url

    def __eq__(self, other):
        if other is None:
            return False
        if self.url == other.url:
            return True
        return False

    def __str__(self):
        return u'%s - %s' % (self.artist, self.title)

    def __repr__(self):
        return self.__str__()


class FreeMusic:
    guid_regex = re.compile("<input type='hidden' name='s' id='s' value='([a-z0-9]+)'")
    operate_regex = re.compile("return operate\(([0-9]+),([0-9]+),([0-9]+),'([a-z0-9]+)',([0-9]+)\);")
    guid = None
    last_search = None

    def login(self):
        conn = httplib2.HTTPConnectionWithTimeout("login.vk.com")

        headers = {'Cookie':"remixchk=5; l=5337115; p=7378d9d80df7781b3849bec8db9bf5cb61a4",
                   'User-Agent': "Tcl http client package 2.7" }
        conn.request('GET', '/', None, headers)
        req = conn.getresponse()

        res = req.read()
        req.close()
        conn.close()

        rem = self.guid_regex.search(res)

        if rem is None or rem.group(1) == 'nonenone':
            raise LoginFailedException

        self.guid = rem.group(1)


    def search(self, query):
        encoded = urllib.urlencode({'section': 'audio', 'q': query})
        headers = {'Cookie': "remixchk=5; remixsid=%s;" % self.guid,
                   'User-Agent': "Tcl http client package 2.7" }
        conn = httplib2.HTTPConnectionWithTimeout("vkontakte.ru")

        conn.request('POST', '/gsearch.php?%s' % encoded, None, headers)
        req = conn.getresponse()

        res = req.read()
        req.close()
        conn.close()

        self.last_search = self._parse_songs(res)

        return self.last_search

    def fetch_details(self, songs = None):
        if songs is None:
            songs = self.last_search

        for song in songs:
            parsed = urllib2.urlparse.urlparse(song.url)
            headers = {'User-Agent': "Tcl http client package 2.7" }
            conn = httplib2.HTTPConnectionWithTimeout(parsed.netloc)

            conn.request('HEAD', parsed.path, None, headers)
            req = conn.getresponse()
            length = req.getheader('Content-Length')

            song.size = int(length)
            song.bitrate = int( song.size * 8 / song.duration / 1000.0)

    def _parse_songs(self, html_response):
        songs = list()
        soup = BeautifulSoup(html_response, convertEntities=BeautifulSoup.ALL_ENTITIES)
        audiorows = soup.findAll('div', {'class': 'audioRow', 'id':re.compile('audio[0-9]+')})

        for row in audiorows:
            song = self._get_song(row)
            if song is None:
                continue
            if song not in songs:
                songs.append(song)
            else:
                del song

        return songs

    def _get_song(self, audiorow):
        song = None
        try:
            playimg = audiorow.find('img', {'class': 'playimg'})
            rem = self.operate_regex.match(playimg.get('onclick'))
            song = Song("http://cs%s.vkontakte.ru/u%s/audio/%s.mp3" % (rem.group(2), rem.group(3), rem.group(4)))
            song.duration = int(rem.group(5))
            song.artist = unicode(audiorow.find('b', {'id':'performer%s' % rem.group(1)}).contents[0]).strip()
            title = audiorow.find('span', {'id':'title%s' % rem.group(1)})
            if title.a is None:
                song.title = unicode(title.contents[0]).strip()
            else:
                song.title = unicode(title.a.contents[0]).strip() # Fix javascript show lyrics
        except Exception as ex:
            raise SongParseError(ex)
        return song

def reporthook(block,blocksize,totalsize):
    sys.stdout.write('\r%d %%' % (block*blocksize/float(totalsize)*100.0))
    sys.stdout.flush()

if __name__ == '__main__':
    from sys import argv
    if len(argv) < 2:
        print 'Usage: ./%s "search term"' % argv[0]
        exit(1)

    fm = FreeMusic()
    try:
        fm.login()
    except LoginFailedException:
        print "Login failed :("
        exit(1)

    fm.search(argv[1])
    print 'found %d' % len(fm.last_search)

    #songs= fm._parse_songs(open("dump.html", "r").read())
    #print songs[2],songs[2].url

    # FIXME: Make interactive menu systerm with browsing and downloading
    # FIXME: possibly also gtk gui :)
    sub = fm.last_search[:1]
    fm.fetch_details(sub)
    for s in sub:
        print u'%s (%.2f MiB, %d kbps)' % (s, s.size/1048576.0, s.bitrate)
        retrieved = urllib.urlretrieve(s.url, reporthook=reporthook)
        dir(retrieved[1])
        os.rename(retrieved[0], u'%s.mp3' % s)
        print "Downloaded %s.mp3" % s
