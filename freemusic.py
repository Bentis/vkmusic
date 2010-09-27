#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Based on PirateApp by thisismyfakemail123 - http://code.google.com/p/pirateapp/
#

import re
import os
import sys
import time
import urllib
import urllib2
import httplib2
from BeautifulSoup import BeautifulSoup

CONSOLE_WIDTH = 80
RESULTS_PER_PAGE = 5
PLAYER = 'vlc'

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


class TextUI:
    freemusic = None
    results = []
    current_offset = 0
    quit = False
    last_update = 0
    last_bytecount = 0
    download_started = 0

    def __init__(self):
        self.freemusic = FreeMusic()
        try:
            self.freemusic.login()
        except LoginFailedException:
            print "Login failed :("
            return None

    def run(self):
        self._show_main_menu()
        while(not self.quit):
            sys.stdout.write("? ")
            command = sys.stdin.readline()
            self._execute_command(command)

    def _show_main_menu(self):
        print "Main menu:"
        print "s <query> - new search"
        print "h - show help"
        print "q - quit"

    def _display_help(self):
        print "Commands:"
        print "s <query> - new search"
        print "q - quit"
        print "n - show next results"
        print "p - show previous results"
        print "d <index> - download song at index <index>"
        print "x - play downloaded song"
        print "r <new> - rename last file to <new>"

    def _execute_command(self, raw_command):
        if len(raw_command) < 1:
            print "invalid command, try again"
            return

        command = raw_command[:1]
        if command == 'q':
            print "Quitting"
            self.quit = True
            return
        elif command == 'h':
            self._display_help()
        elif command == 'n':
            self._next_subresults()
        elif command == 'p':
            self._prev_subresults()
        elif command == 'x':
            # TODO: start player process
            print "Not implemented"
        elif command == 'r':
            # TODO: rename last file
            print "Not implemented"
        elif command == 's':
                self._do_search(raw_command[1:].strip())
        elif command == 'd':
            try:
                index = int(raw_command[1:].strip())
                self._download_song(index)
            except ValueError:
                print "Bad index!"
        else:
            print "invalid command, try agian."

    def _do_search(self, query):
        if len(query) == 0:
            print "missing search term (s <song or artist>)."
            return

        self.results = self.freemusic.search(query)
        self.current_offset = 0

        self._display_results()

    def _display_results(self):
        if len(self.results) == 0:
            print "No results."
            return
        else:
            print "Showing results %d to %d of a total %d:" % (self.current_offset,
                    self.current_offset + RESULTS_PER_PAGE, len(self.results))
            self._display_subresults(self.results[self.current_offset:self.current_offset+RESULTS_PER_PAGE])
            # FIXME: list actual result indexes (result might contain less than RESULTS_PER_PAGE entries)

    def _display_subresults(self, results):
        self.freemusic.fetch_details(results)
        i = 0
        for s in results:
            print u"%d: %s (%.2f MiB, %d kbps)" % (i, s, s.size/1048576.0, s.bitrate)
            i+=1

        print "To download type 'd <index>', use 'n' or 'p' for next or previous results."

    def _next_subresults(self):
        if self.current_offset < len(self.results):
            self.current_offset += RESULTS_PER_PAGE
            self._display_results()
        else:
            print "No more results."

    def _prev_subresults(self):
        if self.current_offset >= RESULTS_PER_PAGE:
            self.current_offset -= RESULTS_PER_PAGE
            self._display_results()
        else:
            print "At the beginning."

    def _get_console_width(self):
        # TODO: Make this dynamic with actual lookup? Pri: LOW
        # Could look at the implementation in python-wget
        return CONSOLE_WIDTH

    def _download_reporthook(self, block, blocksize, totalsize):
        # Dont update for every hook, no point. But run on 100%
        downloaded = block*blocksize
        if ((time.time() - self.last_update < 0.3) and not (downloaded >= totalsize)):
            return

        percent = (downloaded/float(totalsize)*100.0)
        sys.stdout.write('\r%3d%% [' % percent)

        bar_length = self._get_console_width() - 22 - len(str(totalsize))
        bar_filled = int(bar_length/100.0*percent)

        sys.stdout.write('=' * bar_filled)
        sys.stdout.write('>')
        sys.stdout.write(' ' * (bar_length-bar_filled))

        if downloaded >= totalsize: # 100%
            time_used = time.time()-self.download_started
            kilobytes = totalsize/1024.0
            sys.stdout.write("] %.2fMiB in %ds (%d KiB/s)" % (kilobytes/1024.0, time_used, int(kilobytes/time_used)))
            # FIXME: this might smash the console width
        else:
            sys.stdout.write("] %d (%d KiB/s)" % (downloaded,
                    int((downloaded-self.last_bytecount)/(time.time()-self.last_update)/1024.0)))
        sys.stdout.flush()

        self.last_update = time.time()
        self.last_bytecount = downloaded

    def _download_song(self, index):
        song = self.results[index]
        print u"Downloading song '%s'" % song
        #print "debug: %s" % song.url
        self.download_started = time.time()
        self.last_update = time.time()
        self.last_bytecount = 0

        try:
            retrieved = urllib.urlretrieve(song.url, reporthook=self._download_reporthook)
            self.last_filename = u"%s.mp3" % song
            os.rename(retrieved[0], self.last_filename) # defaults to current dir
        except Exception as ex:
            print "Download failed! reason: %s" % ex
            return
        print # newline after download progress.
        print "Saved as %s" % self.last_filename
        print "To play in %s type 'x'" % PLAYER
        # TODO: rename!

if __name__ == '__main__':
    TextUI().run()