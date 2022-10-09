import logging
import time
from sched import scheduler

from PIL import Image
from pypresence import InvalidID

import globals as g
import util
import wrappers.last_fm_user
from wrappers.system_tray_icon import SystemTrayIcon

logger = logging.getLogger("discord_fm").getChild(__name__)


class LoopHandler:
    def __init__(self, tray_icon: SystemTrayIcon):
        self._last_track = None
        self.tray = tray_icon
        self.user = wrappers.last_fm_user.LastFMUser(g.local_settings.get("username"))
        self.sc = scheduler(time.time)

        self.cooldown = g.local_settings.get("cooldown")
        self.misc_cooldown = 15

    def handle_update(self):
        self.sc.enter(self.cooldown, 1, self._lastfm_update, (self.sc,))
        self.sc.enter(self.misc_cooldown, 2, self._misc_update, (self.sc,))
        self.sc.run()

    # noinspection PyUnboundLocalVariable,PyShadowingNames
    def _lastfm_update(self, scheduler):
        if g.current == g.Status.DISABLED or g.current == g.Status.WAITING_FOR_DISCORD:
            self.sc.enter(self.cooldown, 1, self._lastfm_update, (scheduler,))
            return
        elif g.current == g.Status.KILL:
            return

        try:
            track = self.user.now_playing()
        except KeyboardInterrupt:
            return

        if track is not None:
            try:
                g.discord_rp.update_status(track)
                self._last_track = track
            except (BrokenPipeError, InvalidID):
                logger.info("Discord is being closed, will wait for it to open again")
                g.manager.wait_for_discord()
        else:
            logger.debug("Not playing anything")

        if not g.current == g.Status.KILL:
            self.sc.enter(self.cooldown, 1, self._lastfm_update, (scheduler,))

    def _misc_update(self, misc_scheduler):
        logger.debug("Running misc update")
        if g.current == g.Status.DISABLED:
            self.sc.enter(self.misc_cooldown, 2, self._misc_update, (misc_scheduler,))
            return
        elif g.current == g.Status.KILL:
            return

        self.cooldown = g.local_settings.get("cooldown")
        image_path = util.resource_path(
            "resources", "white" if util.check_dark_mode() else "black", "icon.png"
        )
        icon = Image.open(image_path)
        self.tray.ti.icon = icon

        g.local_settings.load()
        # Reload if username has been changed
        if (
            self.user.user.name is not None
            and not g.local_settings.get("username") == self.user.user.name
        ):
            g.manager.reload()

        if not g.current == g.Status.KILL:
            self.sc.enter(self.misc_cooldown, 2, self._misc_update, (misc_scheduler,))

    def reload_lastfm(self):
        username = g.local_settings.get("username")
        logger.debug(f'Reloading LastFMUser with username "{username}"')
        self.user = wrappers.last_fm_user.LastFMUser(username)
