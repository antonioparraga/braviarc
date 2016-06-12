"""
Sony Bravia RC API

By Antonio Parraga Navarro

dedicated to Isabel

"""
import logging
import base64
import json
import socket
import struct
import requests

TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


def _jdata_build(method, params):
    if params:
        ret = json.dumps({"method": method, "params": [params], "id": 1, "version": "1.0"})
    else:
        ret = json.dumps({"method": method, "params": [], "id": 1, "version": "1.0"})
    return ret


def wakeonlan(ethernet_address):
    addr_byte = ethernet_address.split(':')
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


def bravia_auth(ip_address, pin, clientid, nickname):

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
        response = requests.post('http://'+ip_address+'/sony/accessControl',
                                 data=authorization, headers=headers, timeout=TIMEOUT)

    except requests.exceptions.HTTPError as exception_instance:
        _LOGGER.error("[W] HTTPError: " + str(exception_instance))
        return None

    except Exception as exception_instance:  # pylint: disable=broad-except
        _LOGGER.error("[W] Exception: " + str(exception_instance))
        return None

    else:
        _LOGGER.info(json.dumps(response.json(), indent=4))
        return response.cookies

    return None


def send_req_ircc(host, cookies, params):
    """Send an IRCC command via HTTP to Sony Bravia."""
    headers = {'SOAPACTION': 'urn:schemas-sony-com:service:IRCC:1#X_SendIRCC'}
    data = ("<?xml version=\"1.0\"?><s:Envelope xmlns:s=\"http://schemas.xmlsoap.org" +
            "/soap/envelope/\" " +
            "s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body>" +
            "<u:X_SendIRCC " +
            "xmlns:u=\"urn:schemas-sony-com:service:IRCC:1\"><IRCCCode>" +
            params+"</IRCCCode></u:X_SendIRCC></s:Body></s:Envelope>").encode("UTF-8")
    try:
        response = requests.post('http://' + host + '/sony/IRCC',
                                 headers=headers,
                                 cookies=cookies,
                                 data=data,
                                 timeout=TIMEOUT)
    except requests.exceptions.HTTPError as exception_instance:
        _LOGGER.error("[W] HTTPError: " + str(exception_instance))

    except Exception as exception_instance:  # pylint: disable=broad-except
        _LOGGER.error("[W] Exception: " + str(exception_instance))
    else:
        content = response.content
        return content


def bravia_req_json(host, cookies, url, params):
    """ Send request command via HTTP json to Sony Bravia."""
    try:
        response = requests.post('http://'+host+'/'+url,
                                 data=params.encode("UTF-8"),
                                 cookies=cookies,
                                 timeout=TIMEOUT)
    except requests.exceptions.HTTPError as exception_instance:
        _LOGGER.error("[W] HTTPError: " + str(exception_instance))

    except Exception as exception_instance:  # pylint: disable=broad-except
        _LOGGER.error("[W] Exception: " + str(exception_instance))

    else:
        html = json.loads(response.content.decode('utf-8'))
        return html


def load_source_list(host, cookie):
    """ Load source list from Sony Bravia."""
    resp = bravia_req_json(host, cookie, "sony/avContent",
                           _jdata_build("getSourceList", {"scheme": "tv"}))
    if not resp.get('error'):
        original_content_list = []
        results = resp.get('result')[0]
        for result in results:
            if result['source'] == 'tv:dvbc':  # via cable
                resp = bravia_req_json(host, cookie, "sony/avContent",
                                       _jdata_build("getContentList",
                                                    {"source": "tv:dvbc"}))
                if not resp.get('error'):
                    original_content_list.extend(resp.get('result')[0])
            elif result['source'] == 'tv:dvbt':  # via DTT
                resp = bravia_req_json(host, cookie, "sony/avContent",
                                       _jdata_build("getContentList",
                                                    {"source": "tv:dvbt"}))
                if not resp.get('error'):
                    original_content_list.extend(resp.get('result')[0])

        return_value = {}
        for content_item in original_content_list:
            return_value[content_item['title']] = content_item['uri']
        return return_value

