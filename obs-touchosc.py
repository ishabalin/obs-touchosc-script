import os
import sys
import socket
import threading


def activate_virtualenv():
    script_dir = os.path.dirname(__file__)
    python_ver = f'{sys.version_info.major}.{sys.version_info.minor}'
    site_packages_dir = os.path.join(
        script_dir, f'venv/lib/python{python_ver}/site-packages')
    sys.path.insert(0, site_packages_dir)


activate_virtualenv()

from pythonosc.dispatcher import Dispatcher                 # noqa
from pythonosc.osc_server import ThreadingOSCUDPServer      # noqa
from pythonosc.udp_client import SimpleUDPClient            # noqa
from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf  # noqa

try:
    import obspython
except ImportError:
    obspython = None


MAX_SCENES = 8
OSC_PORT = 12345


def button_handler(*args):
    if len(args) == 2:
        name, value = args
        if name.startswith('/scene') and value == 1.0:
            scene_number = int(name[len('/scene'):])
            switch_scene(scene_number)
            update_scene_names()


dispatcher = Dispatcher()
for i in range(MAX_SCENES):
    dispatcher.map(f'/scene{i + 1}', button_handler)


# Example event handler
#
# def ping_handler(*args):
#     print('ping')
#
#
# dispatcher.map(f'/ping', ping_handler)


def get_addr():
    """
    Return current host's IP address.

    """
    return socket.gethostbyname_ex(socket.gethostname())[2][-1]


touchosc_client = None


class MyZeroconfListener:
    """
    Zeroconf service listener.

    Listen for zeroconf events and record TouchOSC client address
    in the `touchosc_client` global variable.

    """
    def remove_service(self, zeroconf, type, name):
        global touchosc_client
        if '._osc._udp' in name and 'OBS_TouchOSC' not in name:
            touchosc_client = None

    def add_service(self, zeroconf, type_, name):
        si = zeroconf.get_service_info(type_=type_, name=name)
        global touchosc_client
        if '._osc._udp' in name and 'OBS_TouchOSC' not in name:
            si = zeroconf.get_service_info(type_=type_, name=name)
            touchosc_client = (si.parsed_addresses()[0], si.port)
            update_scene_names()

    def update_service(self, zeroconf, type_, name):
        global touchosc_client
        if '._osc._udp' in name and 'OBS_TouchOSC' not in name:
            si = zeroconf.get_service_info(type_=type_, name=name)
            touchosc_client = (si.parsed_addresses()[0], si.port)
            update_scene_names()


class MyZeroconfService:
    def __init__(self, port):
        self.port = port
        self.zc = None
        self.browser = None
        self.service_info = None

    def start(self):
        self.zc = Zeroconf()
        self.browser = ServiceBrowser(
            self.zc, '_osc._udp.local.', MyZeroconfListener())
        addr = get_addr()
        self.service_info = ServiceInfo(
            type_='_osc._udp.local.',
            name='OBS_TouchOSC._osc._udp.local.',
            port=self.port,
            addresses=[socket.inet_aton(addr)],
            weight=0,
            priority=0,
        )
        self.zc.register_service(self.service_info)

    def stop(self):
        if self.zc and self.service_info:
            self.zc.unregister_service(self.service_info)
        self.service_info = None
        self.zc = None


class MyOSCServer:
    def __init__(self, port, dispatcher):
        self.port = port
        self._dispatcher = dispatcher
        self._server = None
        self._zeroconf_service = None

    def start(self):
        """
        Start OSC server and register it in zeroconf

        """
        addr = '0.0.0.0'
        self._server = ThreadingOSCUDPServer(
            (addr, self.port), self._dispatcher)
        print('Serving on {}'.format(self._server.server_address))
        threading.Thread(target=self._server.serve_forever).start()
        self._zeroconf_service = MyZeroconfService(self.port)
        self._zeroconf_service.start()

    def stop(self):
        """
        Stop OSC server and unregister it from zeroconf

        """
        if self._zeroconf_service:
            self._zeroconf_service.stop()
        self._zeroconf_service = None
        if self._server:
            self._server.shutdown()
        self._server = None


def update_scene_names():
    """
    Get the list of scenes from the OBS API
    and send it back to TouchOSC app.

    """
    if obspython is None:
        return
    if touchosc_client is None:
        return
    client = SimpleUDPClient(*touchosc_client)
    scenes = obspython.obs_frontend_get_scenes()
    for i, scene in enumerate(scenes[:MAX_SCENES]):
        name = obspython.obs_source_get_name(scene)
        client.send_message(f'/scene{i + 1}/name', name)
        client.send_message(f'/scene{i + 1}-label', name)
        client.send_message(f'/scene{i + 1}/name/label', name)
        client.send_message(f'/scene{i + 1}/name/text', name)
    for i in range(len(scenes), MAX_SCENES):
        client.send_message(f'/scene{i + 1}/name', f'Scene {i + 1}')
    obspython.source_list_release(scenes)


def switch_scene(scene_number):
    """
    Switch `scene_number` where `scene_number` is a 1-indexed number
    of the scene in the list.

    """
    if obspython is None:
        return
    scenes = obspython.obs_frontend_get_scenes()
    for i, scene in enumerate(scenes):
        if i + 1 == scene_number:
            obspython.obs_frontend_set_current_scene(scene)
    obspython.source_list_release(scenes)


my_osc_server = MyOSCServer(OSC_PORT, dispatcher)


def script_load(settings):
    print('obs-touchosc loaded')
    my_osc_server.start()

    # update scene names every 5 seconds
    obspython.timer_add(update_scene_names, 5000)


def script_unload():
    print('obs-touchosc unloaded')
    my_osc_server.stop()
    obspython.timer_remove(update_scene_names)


def script_description():
    return 'Server interface for TouchOSC'


if __name__ == '__main__':
    my_osc_server.start()
