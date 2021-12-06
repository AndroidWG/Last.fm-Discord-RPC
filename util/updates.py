import logging
import os
import requests
import install.windows
from packaging import version
from settings import __version


def check_version_and_download():
    new_release = get_newest_release()
    if new_release is not None:
        path = download_asset(new_release)
        install.windows.do_silent_install(path)
        return True
    else:
        return False


def get_newest_release():
    headers = {"Accept": "application/vnd.github.v3+json",
               "User-Agent": "Discord.fm"}

    request = util.request_handler.attempt_request(
        requests.get,
        "GitHub request",
        url="https://api.github.com/repos/AndroidWG/Discord.fm/releases",
        headers=headers)
    json = request.json()

    for release in json:
        new_version = version.parse(release["tag_name"])
        if new_version > version.parse(__version) or arg_exists("--force-update"):
            logging.info(f"Need to update, newest version: {new_version}")

            for asset in release["assets"]:
                if asset["content_type"] == "application/x-msdownload" and "setup-win" in asset["name"]:
                    return asset

    return None


def download_asset(asset: dict):
    headers = {"Accept": "application/octet-stream",
               "User-Agent": "Discord.fm"}

    request = util.request_handler.attempt_request(
        requests.get,
        "GitHub download",
        timeout=1200,
        url=asset["url"],
        headers=headers)
    response_size = int(request.headers['content-length'])

    logging.info(f"Starting downloading {response_size} bytes...")
    downloaded_path = os.path.join(local_settings.app_data_path, asset["name"])
    with open(downloaded_path, "wb") as file:
        bytes_read = 0

        chunk_size = 512
        for chunk in request.iter_content(chunk_size):
            file.write(chunk)

            bytes_read += chunk_size

    logging.info(f"Successfully finished downloading {asset['name']}")
    return downloaded_path
