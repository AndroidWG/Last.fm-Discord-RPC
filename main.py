import atexit
import logging
import os
import sys
import time
import pystray
import last_fm
import util
import discord_rich_presence as discord_rp
from pypresence import InvalidPipe
from sched import scheduler
from settings import local_settings
from threading import Thread
from PIL import Image
from util import log_setup

__version = "0.3.1"


# From https://stackoverflow.com/a/16993115/8286014
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt) or issubclass(exc_type, SystemExit):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception

user = last_fm.LastFMUser(local_settings.get("username"))
no_song_counter = 0
tray_icon = None
rpc_state = True
enable = True


def toggle_rpc(icon, item):
    global rpc_state, enable
    rpc_state = not item.checked

    if rpc_state:
        discord_rp.connect()
        enable = True
        logging.info("Started update thread again")
    else:
        discord_rp.disconnect()
        enable = False
        logging.info("Sent kill signal to thread")


def close_app(icon=None, item=None):
    global enable
    logging.info("Closing app...")

    try:
        discord_rp.exit_rp()
    except (RuntimeError, AttributeError, AssertionError) as e:
        logging.debug("Caught exception while closing Discord RP", exc_info=e)

    if tray_icon is not None:
        tray_icon.stop()
    enable = False

    sys.exit()


def create_tray_icon():
    global tray_icon

    image_path = util.resource_path("resources/white/icon.png"
                                    if util.check_dark_mode()
                                    else "resources/black/icon.png")
    icon = Image.open(image_path)

    menu = pystray.Menu(
        pystray.MenuItem("Enable Rich Presence", toggle_rpc, checked=lambda item: rpc_state),
        pystray.MenuItem("Open Settings", util.open_settings),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", close_app))
    tray_icon = pystray.Icon("Discord.fm", icon=icon,
                             title="Discord.fm", menu=menu)

    tray_icon.run()


def handle_update():
    cooldown = local_settings.get("cooldown")
    misc_cooldown = 30
    sc = scheduler(time.time)

    # noinspection PyUnboundLocalVariable,PyShadowingNames
    def lastfm_update(scheduler):
        if not enable:
            return

        global no_song_counter
        track = user.now_playing()
        if track is None:
            logging.debug("No song playing")
            no_song_counter += 1

            if no_song_counter == 5:  # Last.fm takes a while to update on song change, make sure user is
                # listening to nothing to clear RP
                discord_rp.disconnect()
        else:
            no_song_counter = 0
            discord_rp.update_status(track)

        sc.enter(cooldown, 1, lastfm_update, (scheduler,))

    def misc_update(misc_scheduler):
        logging.debug("Running misc update")

        if not enable:
            return

        nonlocal cooldown
        cooldown = local_settings.get("cooldown")

        if tray_icon is not None:
            image_path = util.resource_path("resources/white/icon.png"
                                            if util.check_dark_mode() else "resources/black/icon.png")
            icon = Image.open(image_path)
            tray_icon.icon = icon

        sc.enter(misc_cooldown, 2, misc_update, (misc_scheduler,))

    sc.enter(cooldown, 1, lastfm_update, (sc,))
    sc.enter(misc_cooldown, 2, misc_update, (sc,))
    sc.run()


if __name__ == "__main__":
    log_setup.setup_logging("main")
    atexit.register(close_app)

    if not os.path.isfile(util.resource_path(".env")):
        logging.critical(".env file not found, unable to get API keys and data!")
        close_app()

    if local_settings.first_load and util.is_frozen():
        logging.info("First load, opening settings UI and waiting for it to be closed...")
        util.open_settings()

        while not util.process.check_process_running("settings_ui"):
            pass

        while util.process.check_process_running("settings_ui"):
            time.sleep(1)

    if util.process.check_process_running("discord_fm"):
        logging.info("Discord.fm is already running, opening settings")

        util.open_settings()
        close_app()

    if sys.argv.__contains__("-o"):
        logging.info("\"-o\" argument was found, opening settings")
        util.open_settings()

    while True:
        if util.process.check_process_running("Discord", "DiscordCanary"):
            try:
                discord_rp.connect()
            except (FileNotFoundError, InvalidPipe):
                continue
            break
        else:
            time.sleep(8)

    tray_thread = Thread(target=create_tray_icon)
    tray_thread.start()

    try:
        handle_update()
    except (KeyboardInterrupt, SystemExit):
        close_app()
