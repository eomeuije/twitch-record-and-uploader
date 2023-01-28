#!/usr/bin/env python3

# This code is based on tutorial by slicktechies modified as needed to use oauth token from Twitch.
# You can read more details at: https://www.junian.net/2017/01/how-to-record-twitch-streams.html
# original code is from https://slicktechies.com/how-to-watchrecord-twitch-streams-using-livestreamer/
# 24/7/365 NAS adaptation by CuriousTorvald (https://gist.github.com/curioustorvald/f7d1eefe1310efb8d41bee2f48a8e681)
# Twitch Helix API integration by Krepe.Z (https://gist.github.com/krepe90/22a0a6159b024ccf8f67ee034f94c1cc)

# Copyright © 2017, 2019, 2020, 2022 Junian, CuriousTorvald and Krepe.Z
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Only works for Streamlink version >= 4.2.0

import datetime
import logging
import os
import re
import subprocess
import sys
import argparse
import time
import threading
from src.upload.googledrive import Upload
from typing import List, TypedDict, Union
import requests
import json


FILE_NAME_FORMAT = "{user_login} - {stream_started} - {escaped_title}.ts"
TIME_FORMAT = "%y-%m-%d %Hh%Mm%Ss"
INTERNET_TIMEOUT = 15

logger = logging.getLogger()
logger.setLevel(logging.INFO)
fmt = logging.Formatter("{asctime} {levelname} {name} {message}", style="{")
stream_hdlr = logging.StreamHandler()
stream_hdlr.setFormatter(fmt)
logger.addHandler(hdlr=stream_hdlr)


def escape_filename(s: str) -> str:
    """Remove special charactors that cannot use for filename"""
    return re.sub(r"[/\\?%*:|\"<>.\n{}]", "", s)

def truncate_long_name(s: str) -> str:
    return (s[:75] + '..') if len(s) > 77 else s


class StreamData(TypedDict):
    id: str
    user_id: str
    user_login: str
    game_id: str
    game_name: str
    type: str
    title: str
    viewer_count: int
    started_at: str
    language: str
    thumbnail_url: str
    tag_ids: List[str]
    is_mature: bool


class TwitchRecorder:

    def __init__(self, username: str, quality: str, country: str) -> None:
        logger.info("Twitch Recorder initializing start!")

        with open(os.path.join(os.path.dirname(__file__), '../tokens/twitch/twitchAPI.json'), 'r') as file:
            j = json.load(file)
            self.TWITCH_API_CLIENT_ID = j['TWITCH_API_CLIENT_ID']
            self.TWITCH_API_CLIENT_SECRET = j['TWITCH_API_CLIENT_SECRET']
            self.TWITCH_AUTH_TOKEN = j['TWITCH_AUTH_TOKEN']

        self.country = country

        self.client_id = self.TWITCH_API_CLIENT_ID
        self._oauth_token_expires = 0

        self.ffmpeg_path = "ffmpeg"
        self.refresh = 2.0
        self.root_path = os.path.join(os.path.dirname(__file__), '../downloads')

        self.username = username
        self.quality = quality

        self.file_dir = os.path.join(self.root_path, self.username)

        if not self.check_streamlink():
            sys.exit(1)
        self.token_acquired = self.get_oauth_token()
        while not self.token_acquired:
            time.sleep(INTERNET_TIMEOUT)
            self.token_acquired = self.get_oauth_token()
        if not self.check_user_exist():
            sys.exit(1)

        time.sleep(self.refresh)

    def get_oauth_token(self) -> bool:
        """Get oauth token from twitch api server using client id"""
        logger.info("Request oauth token from Twitch API server...")
        try:
            data = {
                "client_id": self.TWITCH_API_CLIENT_ID,
                "client_secret": self.TWITCH_API_CLIENT_SECRET,
                "grant_type": "client_credentials",
                "scope": ""
            }
            resp = requests.post("https://id.twitch.tv/oauth2/token", data=data)
            if resp.status_code != 200:
                return False
            resp_json = resp.json()
            access_token: str = resp_json["access_token"]
            token_type: str = resp_json["token_type"]
            self.oauth_token = f"{token_type.title()} {access_token}"
            self._oauth_token_expires = time.time() + resp_json["expires_in"]
            logger.debug("oauth_token is %s, expires at %d", self.oauth_token, self._oauth_token_expires)
        except requests.RequestException as e:
            logger.error("Fail to get oAuth token: %s", e)
            return False
        else:
            return True

    def check_streamlink(self) -> bool:
        """check if streamlink >= 3.0.0 is installed"""
        try:
            ret = subprocess.check_output(["streamlink", "--version"], universal_newlines=True)
            re_ver = re.search(r"streamlink (\d+)\.(\d+)\.(\d+)", ret, flags=re.IGNORECASE)
            if not re_ver:
                return False
            s_ver = tuple(map(int, re_ver.groups()))
            return s_ver[0] >= 3
        except FileNotFoundError:
            logger.error("Cannot find streamlink! Install streamlink first.")
            return False

    def check_oauth_token(self) -> None:
        """Auto re-request oauth token before it expires"""
        if time.time() + 3600 > self._oauth_token_expires:
            self.get_oauth_token()

    def check_user_exist(self) -> bool:
        """Check if username is vaild (https://dev.twitch.tv/docs/api/reference#get-users)"""
        logger.info("Checking user exists...")
        try:
            header = {
                "Client-ID": self.client_id,
                "Authorization": self.oauth_token
            }
            resp = requests.get(f"https://api.twitch.tv/helix/users?login={self.username}", headers=header)
            if resp.status_code != 200:
                logger.error("HTTP ERROR: %s", resp.status_code)
                logger.debug(resp.text)
                return False
            if not resp.json().get("data"):
                logger.error("Response is empty!")
                return False
        except requests.RequestException as e:
            logger.error("Fail to check user: %s", e)
            return False
        else:
            return True

    def check_streaming(self) -> Union[StreamData, None]:
        """Get stream info (https://dev.twitch.tv/docs/api/reference#get-streams)"""
        try:
            header = {
                "Client-ID": self.client_id,
                "Authorization": self.oauth_token
            }
            resp = requests.get(f"https://api.twitch.tv/helix/streams?user_login={self.username}", headers=header, timeout=15)
            if resp.status_code != 200:
                logger.error("HTTP ERROR: %s", resp.status_code)
                return
            data = resp.json().get("data", [])
            if not data:
                # logger.error("Search result is empty!")
                return
            return data[0]
        except requests.RequestException as e:
            logger.error("Fail to get stream info: %s", e)
            return

    def loop(self):
        """main loop function"""
        logger.info("Loop start!")
        while True:
            stream_data = self.check_streaming()
            if stream_data is None:
                # logger.info("%s is currently offline, checking again in %.1f seconds.", self.username, self.refresh)
                time.sleep(self.refresh)
            else:
                logger.info("%s online. Stream recording in session.", self.username)
                _data = {
                    "escaped_title": truncate_long_name(escape_filename(stream_data["title"])),
                    "stream_started": datetime.datetime.fromisoformat(stream_data["started_at"].replace("Z", "+00:00")).astimezone().strftime(TIME_FORMAT),
                    "record_started": datetime.datetime.now().strftime(TIME_FORMAT)
                }
                file_name = FILE_NAME_FORMAT.format(**stream_data, **_data)
                file_path = os.path.join(self.file_dir, file_name)

                uq_num = 0
                while os.path.exists(file_path):
                    logger.warning("File already exists, will add numbers: %s", file_path)
                    uq_num += 1
                    file_path_no_ext, file_ext = os.path.splitext(file_path)
                    if uq_num > 1 and file_path_no_ext.endswith(f" ({uq_num - 1})"):
                        file_path_no_ext = file_path_no_ext.removesuffix(f" ({uq_num - 1})")
                    file_path = f"{file_path_no_ext} ({uq_num}){file_ext}"

                # start streamlink process
                logger.info("Straming video will save at %s", file_path)

                # vpn = Vpngate(self.country).start_vpn()

                # ret = subprocess.Popen(["streamlink", "--twitch-disable-hosting", "--twitch-disable-ads", "twitch.tv/" + self.username, self.quality, "-o", file_path])

                # get m3u8 link from https://github.com/Kwabang/Twitch-API#hls
                url = "http://localhost:5000/hls?id=" + self.username + "&oauth=" + self.TWITCH_AUTH_TOKEN
                m3u8_link = requests.get(url).text
                m3u8_link = m3u8_link.split('"')[1]
                # print(m3u8_link)

                ret = subprocess.call(["streamlink", "--twitch-disable-hosting", "--twitch-disable-ads", m3u8_link, self.quality, "-o", file_path])

                if ret != 0:
                    logger.warning("Unexpected error.")

                # vpn.kill()

                # end streamlink process
                logger.info("Recording stream is done. Going back to checking...")
                u = Upload()
                thread = threading.Thread(target=u.upload, args=[self.username])
                thread.start()
                time.sleep(self.refresh)

    def run(self):
        """run"""
        if self.refresh < 5:
            print("Check interval should not be lower than 5 seconds.")
            self.refresh = 5
            print("System set check interval to 5 seconds.")
        # create directory for recordedPath and processedPath if not exist
        if not os.path.isdir(self.file_dir):
            os.makedirs(self.file_dir)
        self.loop()