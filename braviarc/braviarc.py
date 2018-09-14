"""
Sony Bravia RC API

By Antonio Parraga Navarro

dedicated to Isabel

"""
import logging
import base64
import collections
import json
import socket
import struct
import requests

TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


class BraviaRC:

    def __init__(self, host, mac=None):  # mac address is optional but necessary if we want to turn on the TV
        """Initialize the Sony Bravia RC class."""

        self._host = host
        self._mac = mac
        self._cookies = None
        self._commands = []
        self._content_mapping = []
        self._app_list = {}

    def _jdata_build(self, method, params):
        if params:
            ret = json.dumps({"method": method, "params": [params], "id": 1, "version": "1.0"})
        else:
            ret = json.dumps({"method": method, "params": [], "id": 1, "version": "1.0"})
        return ret

    def connect(self, pin, clientid, nickname):
        """Connect to TV and get authentication cookie.

        Parameters
        ---------
        pin: str
            Pin code show by TV (or 0000 to get Pin Code).
        clientid: str
            Client ID.
        nickname: str
            Client human friendly name.

        Returns
        -------
        bool
            True if connected.
        """
        authorization = json.dumps(
            {"method": "actRegister",
             "params": [{"clientid": clientid,
                         "nickname": nickname,
                         "level": "private"},
                        [{"value": "yes",
                          "function": "WOL"}]],
             "id": 1,
             "version": "1.0"}
        ).encode('utf-8')

        headers = {}
        if pin:
            username = ''
            base64string = base64.encodebytes(('%s:%s' % (username, pin)).encode()) \
                .decode().replace('\n', '')
            headers['Authorization'] = "Basic %s" % base64string
            headers['Connection'] = "keep-alive"

        try:
            response = requests.post('http://'+self._host+'/sony/accessControl',
                                     data=authorization, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()

        except requests.exceptions.HTTPError as exception_instance:
            _LOGGER.error("[W] HTTPError: " + str(exception_instance))
            return False

        except Exception as exception_instance:  # pylint: disable=broad-except
            _LOGGER.error("[W] Exception: " + str(exception_instance))
            return False

        else:
            resp = response.json()
            _LOGGER.debug(json.dumps(resp, indent=4))
            if resp is None or not resp.get('error'):
                self._cookies = response.cookies
                return True

        return False

    def is_connected(self):
        if self._cookies is None:
            return False
        else:
            return True

    def _wakeonlan(self):
        if self._mac is not None:
            addr_byte = self._mac.split(':')
            hw_addr = struct.pack('BBBBBB', int(addr_byte[0], 16),
                                  int(addr_byte[1], 16),
                                  int(addr_byte[2], 16),
                                  int(addr_byte[3], 16),
                                  int(addr_byte[4], 16),
                                  int(addr_byte[5], 16))
            msg = b'\xff' * 6 + hw_addr * 16
            socket_instance = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            socket_instance.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            socket_instance.sendto(msg, ('<broadcast>', 9))
            socket_instance.close()

    def send_req_ircc(self, params, log_errors=True):
        """Send an IRCC command via HTTP to Sony Bravia."""
        headers = {'SOAPACTION': '"urn:schemas-sony-com:service:IRCC:1#X_SendIRCC"'}
        data = ("<?xml version=\"1.0\"?><s:Envelope xmlns:s=\"http://schemas.xmlsoap.org" +
                "/soap/envelope/\" " +
                "s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body>" +
                "<u:X_SendIRCC " +
                "xmlns:u=\"urn:schemas-sony-com:service:IRCC:1\"><IRCCCode>" +
                params+"</IRCCCode></u:X_SendIRCC></s:Body></s:Envelope>").encode("UTF-8")
        try:
            response = requests.post('http://' + self._host + '/sony/IRCC',
                                     headers=headers,
                                     cookies=self._cookies,
                                     data=data,
                                     timeout=TIMEOUT)
        except requests.exceptions.HTTPError as exception_instance:
            if log_errors:
                _LOGGER.error("HTTPError: " + str(exception_instance))

        except Exception as exception_instance:  # pylint: disable=broad-except
            if log_errors:
                _LOGGER.error("Exception: " + str(exception_instance))
        else:
            content = response.content
            return content

    def bravia_req_json(self, url, params, log_errors=True):
        """ Send request command via HTTP json to Sony Bravia."""
        try:
            response = requests.post('http://'+self._host+'/'+url,
                                     data=params.encode("UTF-8"),
                                     cookies=self._cookies,
                                     timeout=TIMEOUT)
        except requests.exceptions.HTTPError as exception_instance:
            if log_errors:
                _LOGGER.error("HTTPError: " + str(exception_instance))

        except Exception as exception_instance:  # pylint: disable=broad-except
            if log_errors:
                _LOGGER.error("Exception: " + str(exception_instance))

        else:
            html = json.loads(response.content.decode('utf-8'))
            return html

    def send_command(self, command):
        """Sends a command to the TV."""
        self.send_req_ircc(self.get_command_code(command))

    def get_source(self, source):
        """Returns list of Sources"""
        original_content_list = []
        content_index = 0
        while True:
            resp = self.bravia_req_json("sony/avContent",
                                        self._jdata_build("getContentList", {"source": source, "stIdx": content_index}))
            if not resp.get('error'):
                if len(resp.get('result')[0]) == 0:
                    break
                else:
                    content_index = resp.get('result')[0][-1]['index']+1
                original_content_list.extend(resp.get('result')[0])
            else:
                break
        return original_content_list

    def load_source_list(self):
        """ Load source list from Sony Bravia."""
        original_content_list = []
        resp = self.bravia_req_json("sony/avContent",
                                    self._jdata_build("getSourceList", {"scheme": "tv"}))
        if not resp.get('error'):
            results = resp.get('result')[0]
            for result in results:
                if result['source'] in ['tv:dvbc', 'tv:dvbt', 'tv:isdbt', 'tv:isdbbs', 'tv:isdbcs']:  # tv:dvbc = via cable, tv:dvbt = via DTT, tv:isdb* = via Japanese
                    original_content_list.extend(self.get_source(result['source']))

        resp = self.bravia_req_json("sony/avContent",
                                    self._jdata_build("getSourceList", {"scheme": "extInput"}))
        if not resp.get('error'):
            results = resp.get('result')[0]
            for result in results:
                if result['source'] in ('extInput:hdmi', 'extInput:composite', 'extInput:component'):  # physical inputs
                    resp = self.bravia_req_json("sony/avContent",
                                                self._jdata_build("getContentList", result))
                    if not resp.get('error'):
                        original_content_list.extend(resp.get('result')[0])

        return_value = collections.OrderedDict()
        for content_item in original_content_list:
            return_value[content_item['title']] = content_item['uri']
        return return_value

    def get_playing_info(self):
        return_value = {}
        resp = self.bravia_req_json("sony/avContent", self._jdata_build("getPlayingContentInfo", None))
        if resp is not None and not resp.get('error'):
            playing_content_data = resp.get('result')[0]
            return_value['programTitle'] = playing_content_data.get('programTitle')
            return_value['title'] = playing_content_data.get('title')
            return_value['programMediaType'] = playing_content_data.get('programMediaType')
            return_value['dispNum'] = playing_content_data.get('dispNum')
            return_value['source'] = playing_content_data.get('source')
            return_value['uri'] = playing_content_data.get('uri')
            return_value['durationSec'] = playing_content_data.get('durationSec')
            return_value['startDateTime'] = playing_content_data.get('startDateTime')
        return return_value

    def get_power_status(self):
        """Get power status: off, active, standby"""
        return_value = 'off' # by default the TV is turned off
        try:
            resp = self.bravia_req_json("sony/system", self._jdata_build("getPowerStatus", None), False)
            if resp is not None and not resp.get('error'):
                power_data = resp.get('result')[0]
                return_value = power_data.get('status')
        except:  # pylint: disable=broad-except
            pass
        return return_value

    def _refresh_commands(self):
        resp = self.bravia_req_json("sony/system", self._jdata_build("getRemoteControllerInfo", None))
        if not resp.get('error'):
            self._commands = resp.get('result')[1]
        else:
            _LOGGER.error("JSON request error: " + json.dumps(resp, indent=4))

    def get_command_code(self, command_name):
        if len(self._commands) == 0:
            self._refresh_commands()
        for command_data in self._commands:
            if command_data.get('name') == command_name:
                return command_data.get('value')
        return None

    def get_volume_info(self):
        """Get volume info."""
        resp = self.bravia_req_json("sony/audio", self._jdata_build("getVolumeInformation", None))
        if not resp.get('error'):
            results = resp.get('result')[0]
            for result in results:
                if result.get('target') == 'speaker':
                    return result
        else:
            _LOGGER.error("JSON request error:" + json.dumps(resp, indent=4))
        return None

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self.bravia_req_json("sony/audio", self._jdata_build("setAudioVolume", {"target": "speaker",
                                                                                "volume": volume * 100}))

    def _recreate_auth_cookie(self):
        """
        The default cookie is for URL/sony. For some commands we need it for the root path
        """
        cookies = requests.cookies.RequestsCookieJar()
        cookies.set("auth", self._cookies.get("auth"))
        return cookies

    def load_app_list(self, log_errors=True):
        """Get the list of installed apps"""
        headers = {}
        parsed_objects = {}

        try:
            cookies = self._recreate_auth_cookie()
            response = requests.get('http://' + self._host + '/DIAL/sony/applist',
                                     cookies=cookies,
                                     timeout=TIMEOUT)
        except requests.exceptions.HTTPError as exception_instance:
            if log_errors:
                _LOGGER.error("HTTPError: " + str(exception_instance))

        except Exception as exception_instance:  # pylint: disable=broad-except
            if log_errors:
                _LOGGER.error("Exception: " + str(exception_instance))
        else:
            content = response.content
            from xml.dom import minidom
            parsed_xml = minidom.parseString(content)
            for obj in parsed_xml.getElementsByTagName("app"):
                if obj.getElementsByTagName("name")[0].firstChild and obj.getElementsByTagName("id")[0].firstChild:
                    parsed_objects[str(obj.getElementsByTagName("name")[0].firstChild.nodeValue)] = str(obj.getElementsByTagName("id")[0].firstChild.nodeValue)

        return parsed_objects

    def start_app(self, app_name, log_errors=True):
        """Start an app by name"""
        if len(self._app_list) == 0:
            self._app_list = self.load_app_list(log_errors=log_errors)
        if app_name in self._app_list:
            return self._start_app(self._app_list[app_name], log_errors=log_errors)

    def _start_app(self, app_id, log_errors=True):
        """Start an app by id"""
        headers = {}
        try:
            cookies = self._recreate_auth_cookie()
            response = requests.post('http://' + self._host + '/DIAL/apps/' + app_id,
                                     cookies=cookies,
                                     timeout=TIMEOUT)
        except requests.exceptions.HTTPError as exception_instance:
            if log_errors:
                _LOGGER.error("HTTPError: " + str(exception_instance))

        except Exception as exception_instance:  # pylint: disable=broad-except
            if log_errors:
                _LOGGER.error("Exception: " + str(exception_instance))
        else:
            content = response.content
            return content

    def turn_on(self):
        """Turn the media player on."""
        self._wakeonlan()
        # Try using the power on command incase the WOL doesn't work
        if self.get_power_status() != 'active':
            self.send_req_ircc(self.get_command_code('TvPower'))

    def turn_off(self):
        """Turn off media player."""
        self.send_req_ircc(self.get_command_code('PowerOff'))

    def volume_up(self):
        """Volume up the media player."""
        self.send_req_ircc(self.get_command_code('VolumeUp'))

    def volume_down(self):
        """Volume down media player."""
        self.send_req_ircc(self.get_command_code('VolumeDown'))

    def mute_volume(self, mute):
        """Send mute command."""
        self.send_req_ircc(self.get_command_code('Mute'))

    def select_source(self, source):
        """Set the input source."""
        if len(self._content_mapping) == 0:
            self._content_mapping = self.load_source_list()
        if source in self._content_mapping:
            uri = self._content_mapping[source]
            self.play_content(uri)

    def play_content(self, uri):
        """Play content by URI."""
        self.bravia_req_json("sony/avContent", self._jdata_build("setPlayContent", {"uri": uri}))

    def media_play(self):
        """Send play command."""
        self.send_req_ircc(self.get_command_code('Play'))

    def media_pause(self):
        """Send media pause command to media player."""
        self.send_req_ircc(self.get_command_code('Pause'))

    def media_next_track(self):
        """Send next track command."""
        self.send_req_ircc(self.get_command_code('Next'))

    def media_previous_track(self):
        """Send the previous track command."""
        self.send_req_ircc(self.get_command_code('Prev'))
