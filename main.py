#!/usr/bin/env python3

from PIL import Image, ImageColor, UnidentifiedImageError
from io import BytesIO
import json
import math
import os
import os.path
import random
import threading
import time
import sys

from bs4 import BeautifulSoup
import click
# noinspection PyUnresolvedReferences
from loguru import logger
import requests
# noinspection PyUnresolvedReferences
from websocket import create_connection


class ColorMapper:
    COLORS = [
        ('0', '#6D001A', 'burgundy'),
        ('1', '#BE0039', 'dark red'),
        ('2', '#FF4500', 'red'),
        ('3', '#FFA800', 'orange'),
        ('4', '#FFD635', 'yellow'),
        ('5', '#FFF8B8', 'pale yellow'),
        ('6', '#00A368', 'dark green'),
        ('7', '#00CC78', 'green'),
        ('8', '#7EED56', 'light green'),
        ('9', '#00756F', 'dark teal'),
        ('10', '#009EAA', 'teal'),
        ('11', '#00CCC0', 'light teal'),
        ('12', '#2450A4', 'dark blue'),
        ('13', '#3690EA', 'blue'),
        ('14', '#51E9F4', 'light blue'),
        ('15', '#493AC1', 'indigo'),
        ('16', '#6A5CFF', 'periwinkle'),
        ('17', '#94B3FF', 'lavender'),
        ('18', '#811E9F', 'dark purple'),
        ('19', '#B44AC0', 'purple'),
        ('20', '#E4ABFF', 'pale purple'),
        ('21', '#DE107F', 'magenta'),
        ('22', '#FF3881', 'pink'),
        ('23', '#FF99AA', 'light pink'),
        ('24', '#6D482F', 'dark brown'),
        ('25', '#9C6926', 'brown'),
        ('26', '#FFB470', 'beige'),
        ('27', '#000000', 'black'),
        ('28', '#515252', 'dark gray'),
        ('29', '#898D90', 'gray'),
        ('30', '#D4D7D9', 'light gray'),
        ('31', '#E9EBED', 'white')
    ]
    RGB_COLORS = [ImageColor.getcolor(c[1], "RGB") for c in COLORS]

    @staticmethod
    def rgb_to_hex(rgb: tuple):
        """Convert rgb tuple to hexadecimal string."""
        return ("#%02x%02x%02x" % rgb).upper()

    @classmethod
    def closest_color(cls, target_rgb: tuple):
        """Find the closest rgb color from palette to a target rgb color"""
        r, g, b = target_rgb[:3]
        color_diffs = []
        for i, color in enumerate(cls.RGB_COLORS):
            cr, cg, cb = color
            color_diff = math.sqrt((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2)
            color_diffs.append((color_diff, i))
        return min(color_diffs)[1]


class RedditClient:
    def __init__(self, thread_id, user, password, proxies=None):
        self.thread_id = thread_id
        self.user = user
        self.password = password
        self.proxies = list(proxies or [])
        self._csrf_token = None
        self._token = None
        self._ttl = None
        self._session = None

    def get_random_proxy(self):
        if self.proxies:
            return random.choice(self.proxies)

    @property
    def session(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/80.0.3987.149 Safari/537.36'
            })
        return self._session

    @property
    def csrf_token(self):
        if self._csrf_token is None or self._ttl and self._ttl < time.perf_counter():
            r = self.session.get('https://www.reddit.com/login')
            login_get_soup = BeautifulSoup(r.content, "html.parser")
            self._csrf_token = login_get_soup.find(
                "input", {"name": "csrf_token"}
            )["value"]
        return self._csrf_token

    @property
    def token(self):
        if self._token is None or self._ttl and self._ttl < time.perf_counter():
            data = {
                "username": self.user,
                "password": self.password,
                "dest": "https://new.reddit.com/",
                "csrf_token": self.csrf_token,
            }
            retry, max_retries, resp = 0, 3, None
            while retry < max_retries:
                retry += 1
                try:
                    r = self.session.post(
                        "https://www.reddit.com/login",
                        data=data,
                        proxies=self.get_random_proxy(),
                    )
                    if r.status_code == 200:
                        r = self.session.get(r.json()['dest'], proxies=self.get_random_proxy())
                        soup = BeautifulSoup(r.content, features="html.parser")
                        soup = soup.find("script", {"id": "data"}).contents[0][len("window.__r = "):-1]
                        resp = json.loads(soup)
                        break
                except Exception as e:
                    logger.warning(f'cannot get token for {self}: {e}')
            if not resp:
                raise RuntimeError(f"Authorization failed for {self}")
            resp = resp["user"]["session"]
            self._token = resp["accessToken"]
            self._ttl = int(resp['expiresIn'] / 1000) + 1 + time.perf_counter()
        return self._token

    def set_pixel(self, x, y, color_index):
        if not self._DETAILS:
            self.load_board()
        height, width = self._DETAILS['canvasHeight'], self._DETAILS['canvasWidth']
        for canvas in self._DETAILS['canvasConfigurations']:
            if canvas['dx'] <= x < canvas['dx'] + width and canvas['dy'] <= y < canvas['dy'] + height:
                canvas_x = x - canvas['dx']
                canvas_y = y - canvas['dy']
                canvas_index = canvas['index']
                return self._set_pixel(canvas_index, canvas_x, canvas_y, color_index)

    def _set_pixel(self, canvas_index, canvas_x, canvas_y, color_index):
        canvas = self._DETAILS['canvasConfigurations'][canvas_index]
        logger.info(
            "Thread #{} : Attempting to place {} pixel at {}, {}",
            self.thread_id,
            ColorMapper.COLORS[color_index][1],
            canvas_x + canvas['dx'],
            canvas_y + canvas['dy'],
        )

        url = "https://gql-realtime-2.reddit.com/query"

        payload = json.dumps(
            {
                "operationName": "setPixel",
                "variables": {
                    "input": {
                        "actionName": "r/replace:set_pixel",
                        "PixelMessageData": {
                            "coordinate": {"x": canvas_x, "y": canvas_y},
                            "colorIndex": color_index,
                            "canvasIndex": canvas_index,
                        },
                    }
                },
                "query": "mutation setPixel($input: ActInput!) {\n  act(input: $input) {\n    data {\n      ... on "
                         "BasicMessage {\n        id\n        data {\n          ... on "
                         "GetUserCooldownResponseMessageData {\n            nextAvailablePixelTimestamp\n            "
                         "__typename\n          }\n          ... on SetPixelResponseMessageData {\n            "
                         "timestamp\n            __typename\n          }\n          __typename\n        }\n        "
                         "__typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
            }
        )
        headers = {
            "origin": "https://hot-potato.reddit.com",
            "referer": "https://hot-potato.reddit.com/",
            "apollographql-client-name": "mona-lisa",
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
        }

        response = requests.post(
            url, headers=headers, data=payload, proxies=self.get_random_proxy()
        )
        logger.debug("Thread #{} : Received response: {}", self.thread_id, response.text)

        # There are 2 different JSON keys for responses to get the next timestamp.
        # If we don't get data, it means we've been rate limited.
        # If we do, a pixel has been successfully placed.
        resp = response.json()
        if resp["data"] is None:
            # wait_time = resp["errors"][0]["extensions"]["nextAvailablePixelTs"] // 1000
            logger.error("Thread #{} : Failed placing pixel: rate limited", self.thread_id)
        else:
            # wait_time = resp["data"]["act"]["data"][0]["data"]["nextAvailablePixelTimestamp"] // 1000
            logger.info("Thread #{} : Succeeded placing pixel", self.thread_id)
            return True

    _DETAILS = None
    _BOARD = None
    _TTL = None
    _LOCK = threading.Lock()

    @classmethod
    def get_board(cls, client, x, y, dx, dy):
        with cls._LOCK:
            if cls._BOARD is None or cls._TTL and cls._TTL < time.perf_counter():
                im = client.load_board()
                ret = []
                for i in range(x, x + dx):
                    col = []
                    for j in range(y, y + dy):
                        p = im.getpixel((i, j))
                        color_index = ColorMapper.closest_color(p)
                        col.append(color_index)
                    ret.append(col)
                cls._BOARD = ret
                cls._TTL = time.perf_counter() + 60
        return cls._BOARD

    def load_board(self):
        logger.debug("connecting and obtaining board images")
        retry, max_retries, data = 0, 3, None
        ws = None
        while retry < max_retries:
            retry += 1
            try:
                ws = create_connection(
                    "wss://gql-realtime-2.reddit.com/query",
                    origin="https://hot-potato.reddit.com",
                )
                break
            except Exception as e:
                logger.warning(f'cannot get websocket for {self}: {e}')
                time.sleep(30)
        if not ws:
            raise RuntimeError(f"Cannot get websocket for {self}")
        ws.send(
            json.dumps(
                {
                    "type": "connection_init",
                    "payload": {"Authorization": "Bearer " + self.token},
                }
            )
        )
        while True:
            msg = ws.recv()
            if msg is None:
                logger.error("Reddit failed to acknowledge connection_init")
                exit()
            if msg.startswith('{"type":"connection_ack"}'):
                logger.debug("Connected to WebSocket server")
                break
        logger.debug("Obtaining Canvas information")
        ws.send(
            json.dumps(
                {
                    "id": "1",
                    "type": "start",
                    "payload": {
                        "variables": {
                            "input": {
                                "channel": {
                                    "teamOwner": "AFD2022",
                                    "category": "CONFIG",
                                }
                            }
                        },
                        "extensions": {},
                        "operationName": "configuration",
                        "query": "subscription configuration($input: SubscribeInput!) {\n  subscribe(input: $input) {"
                                 "\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... "
                                 "on ConfigurationMessageData {\n          colorPalette {\n            colors {\n     "
                                 "         hex\n              index\n              __typename\n            }\n        "
                                 "    __typename\n          }\n          canvasConfigurations {\n            index\n  "
                                 "          dx\n            dy\n            __typename\n          }\n          "
                                 "canvasWidth\n          canvasHeight\n          __typename\n        }\n      }\n     "
                                 " __typename\n    }\n    __typename\n  }\n}\n",
                    },
                }
            )
        )

        while True:
            canvas_payload = json.loads(ws.recv())
            if canvas_payload["type"] == "data":
                canvas_details = canvas_payload["payload"]["data"]["subscribe"]["data"]
                logger.debug("Canvas config: {}", canvas_payload)
                break

        canvas_sockets = []
        self._DETAILS = canvas_details

        for canvas in canvas_details["canvasConfigurations"]:
            i = canvas["index"]
            canvas_sockets.append(i)
            logger.debug("Creating canvas socket {}", i)

            ws.send(
                json.dumps(
                    {
                        "id": str(i),
                        "type": "start",
                        "payload": {
                            "variables": {
                                "input": {
                                    "channel": {
                                        "teamOwner": "AFD2022",
                                        "category": "CANVAS",
                                        "tag": str(i),
                                    }
                                }
                            },
                            "extensions": {},
                            "operationName": "replace",
                            "query": "subscription replace($input: SubscribeInput!) {\n  subscribe(input: $input) {\n "
                                     "   id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... "
                                     "on FullFrameMessageData {\n          __typename\n          name\n          "
                                     "timestamp\n        }\n        ... on DiffFrameMessageData {\n          "
                                     "__typename\n          name\n          currentTimestamp\n          "
                                     "previousTimestamp\n        }\n      }\n      __typename\n    }\n    "
                                     "__typename\n  }\n}\n",
                        },
                    }
                )
            )

        imgs = []
        logger.debug("A total of {} canvas sockets opened", len(canvas_sockets))
        while len(canvas_sockets) > 0:
            temp = json.loads(ws.recv())
            logger.debug("Waiting for WebSocket message")
            if temp["type"] == "data":
                logger.debug("Received WebSocket data type message")
                msg = temp["payload"]["data"]["subscribe"]
                if msg["data"]["__typename"] == "FullFrameMessageData":
                    logger.debug("Received full frame message")
                    img_id = int(temp["id"])
                    logger.debug("Image ID: {}", img_id)
                    if img_id in canvas_sockets:
                        logger.debug("Getting image: {}", msg["data"]["name"])
                        imgs.append(
                            [
                                img_id,
                                Image.open(
                                    BytesIO(
                                        requests.get(
                                            msg["data"]["name"], stream=True
                                        ).content
                                    )
                                ),
                            ]
                        )
                        canvas_sockets.remove(img_id)
                        logger.debug(
                            "Canvas sockets remaining: {}", len(canvas_sockets)
                        )

        for canvas in canvas_details["canvasConfigurations"]:
            i = canvas["index"]
            ws.send(json.dumps({"id": str(i), "type": "stop"}))
        ws.close()

        y, x = canvas_details['canvasHeight'], canvas_details['canvasWidth']
        new_img_width = max(canvas['dx'] + x for canvas in canvas_details['canvasConfigurations'])
        logger.debug("New image width: {}", new_img_width)
        new_img_height = max(canvas['dy'] + y for canvas in canvas_details['canvasConfigurations'])
        logger.debug("New image height: {}", new_img_height)

        new_img = Image.new("RGB", (new_img_width, new_img_height))
        for idx, img in enumerate(sorted(imgs)):
            logger.debug("Adding image (ID {}): {}", img[0], img[1])
            canvas = canvas_details["canvasConfigurations"][idx]
            new_img.paste(img[1], (canvas['dx'], canvas['dy']))
        return new_img


class PlaceClient:
    def __init__(self, config: dict, image: list):
        self.pixel_x_start, self.pixel_y_start = config["image_start_coords"]
        self.image = image
        self.image_size = len(image), len(image[0])

        # In seconds
        self.delay_between_launches = int(config.get('thread_delay') or 3)
        self.proxies = get_proxies(config.get('proxies'))

        # Auth
        self.workers = config['workers']
        self.access_tokens = {}
        self.access_token_expires = {}

    def start(self):
        threads = []
        for index, worker in enumerate(self.workers):
            t = threading.Thread(
                target=self.task,
                args=(index, worker)
            )
            t.start()
            threads.append(t)
            # exit(1)
            time.sleep(self.delay_between_launches)
        for t in threads:
            t.join()

    # Draw the input image
    def task(self, index, name):
        worker = self.workers[name]
        client = RedditClient(index, name, worker['password'])
        logger.info(f"Thread #{index} :: token {client.token}")

        # Whether image should keep drawing itself
        next_pixel_placement_time = 0
        # note: Reddit limits us to place 1 pixel every 5 minutes, so I am setting it to
        # 5 minutes and 30 seconds per pixel
        pixel_place_frequency = 305
        worker_x_start, worker_y_start = worker["start_coords"]
        worker_x_stop, worker_y_stop = worker["stop_coords"]

        while True:
            pc = time.perf_counter()
            time_until_next_draw = next_pixel_placement_time - pc
            if time_until_next_draw > 10000:
                logger.warning(f"Thread #{index} :: CANCELLED :: Rate-Limit Banned")
                break
            elif time_until_next_draw > 0:
                msg = "sleeping for {} seconds".format(time_until_next_draw)
                logger.info(f"Thread #{index} :: {msg}")
                time.sleep(time_until_next_draw)
            b = client.get_board(client, self.pixel_x_start, self.pixel_y_start, *self.image_size)
            a = self.image
            changed, stopped = False, False
            for i in range(worker_x_start, worker_x_stop):
                for j in range(worker_y_start, worker_y_stop):
                    if a[i][j] != b[i][j]:
                        if client.set_pixel(i + self.pixel_x_start, j + self.pixel_y_start, a[i][j]):
                            b[i][j] = a[i][j]
                            changed = True
                        else:
                            stopped = True
                        break
                if changed or stopped:
                    break
            next_pixel_placement_time = time.perf_counter() + pixel_place_frequency


def get_json_data(config_path):
    if not os.path.exists(config_path):
        exit("No config.json file found. Read the README")
    # To not keep file open whole execution time
    with open(config_path) as fh:
        return json.load(fh)


def load_image(image_path):
    # Read and load the image to draw and get its dimensions
    im = None

    try:
        im = Image.open(image_path)
    except UnidentifiedImageError:
        logger.fatal("File found, but couldn't identify image format")
        logger.exception("File found, but couldn't identify image format")
    except Exception as e:
        logger.exception(f"Failed to load image due to {e}")
        exit(1)

    # Convert all images to RGBA - Transparency should only be supported with PNG
    if im.mode != "RGBA":
        im = im.convert("RGBA")
        logger.info("Converted to rgba")
    logger.info("Loaded image size: {}", im.size)
    ret = []
    for i in range(im.size[0]):
        col = []
        for j in range(im.size[1]):
            p = im.getpixel((i, j))
            color_index = ColorMapper.closest_color(p)
            col.append(color_index)
        ret.append(col)
    return ret


def get_proxies(proxies):
    ret = None
    if not proxies:
        pass
    elif isinstance(proxies, list):
        ret = [{'https': line, 'http': line} for line in proxies]
    elif os.path.exists(proxies):
        ret = []
        with open(proxies) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                ret.append({'https': line, 'http': line})
    return ret


@click.command()
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Enable debug mode. Prints debug messages to the console.",
)
@click.option(
    "-c",
    "--config",
    default="config.json",
    help="Location of config.json",
)
def main(debug: bool, config: str):
    config = get_json_data(config)
    image = load_image(config["image_path"])

    if not debug:
        # default loguru level is DEBUG
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    client = PlaceClient(config, image)
    # Start everything
    client.start()


if __name__ == "__main__":
    main()
