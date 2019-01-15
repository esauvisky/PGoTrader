import argparse
import asyncio
import logging
import re
from sys import platform

import pyocr
import yaml

from pokemonlib import PokemonGo

from colorlog import ColoredFormatter

logger = logging.getLogger('ivcheck')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = ColoredFormatter(
    "  %(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

RE_WAITING_TRADE = re.compile(
    "^Waiting for (.+) to be available for trading.$")
POKEMON_TO_TRADE = "POKEMON TO TRADE"


class CalcyIVError(Exception):
    pass


class RedBarError(Exception):
    pass


TRADE_POKEMON_SUFFIX = ".TRADE"


class Main:
    def __init__(self, args):
        with open(args.config, "r") as f:
            self.config = yaml.load(f)
        self.args = args
        tools = pyocr.get_available_tools()
        self.tool = tools[0]

    async def tap(self, location):
        await self.p.tap(*self.config['locations'][location])
        if location in self.config['waits']:
            await asyncio.sleep(self.config['waits'][location])

    async def swipe(self, location, duration):
        await self.p.swipe(
            self.config['locations'][location][0],
            self.config['locations'][location][1],
            self.config['locations'][location][0],
            self.config['locations'][location][1],
            duration
        )
        if location in self.config['waits']:
            await asyncio.sleep(self.config['waits'][location])

    async def start(self):
        self.p = PokemonGo()
        await self.p.set_device(self.args.device_id)
        # await self.p.start_logcat()
        while True:
            await self.tap('trade_button')
            # Wait for trade to start
            while True:
                screencap = await self.p.screencap()
                crop = screencap.crop(self.config['locations']['waiting_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                match = RE_WAITING_TRADE.match(text)
                if match:
                    print(text)
                    continue
                else:
                    crop = screencap.crop(
                        self.config['locations']['pokemon_to_trade_box'])
                    text = self.tool.image_to_string(crop).replace("\n", " ")
                    if text == "POKEMON TO TRADE":
                        print("Pokemon to trade screen reached")
                        break

            # Filter pokemon list
            await self.tap("search_button")
            await self.p.text(TRADE_POKEMON_SUFFIX)
            await asyncio.sleep(1)

            while True:  # Check a pokemon is available and has the correct name
                screencap = await self.p.screencap()
                crop = screencap.crop(
                    self.config['locations']['first_pokemon_name_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                if text == TRADE_POKEMON_SUFFIX:
                    break
                print("Pokemon name is incorrect, got {}".format(text))

            await self.tap("first_pokemon")  # Dismiss keyboard
            await self.tap("first_pokemon")  # Dismiss keyboard

            while True:
                screencap = await self.p.screencap()
                crop = screencap.crop(
                    self.config['locations']['next_button_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                if text != "NEXT":
                    print("Waiting for next, got", text)
                    continue
                print("Found next button")
                crop = screencap.crop(
                    self.config['locations']['name_at_next_screen_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                if text != TRADE_POKEMON_SUFFIX:
                    print("Pokemons name is wrong, got", text)
                    continue
                await self.tap("next_button")
                break

            while True:
                screencap = await self.p.screencap()
                crop = screencap.crop(
                    self.config['locations']['confirm_button_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                if text != "CONFIRM":
                    print("Waiting for confirm, got", text)
                    continue
                print("Found confirm button")

                crop = screencap.crop(self.config['locations']['stardust_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                if text != "100":
                    print("Expecting 100 stardust cost, got",
                          text)
                    return
                crop = screencap.crop(
                    self.config['locations']['trade_name_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                crop = screencap.crop(
                    self.config['locations']['trade_name_box_alt'])
                text2 = self.tool.image_to_string(crop).replace("\n", " ")
                if text != TRADE_POKEMON_SUFFIX and text2 != TRADE_POKEMON_SUFFIX:
                    print("Pokemon name is wrong", text)
                    return
                print("Confirming trade")
                await self.tap("confirm_button")
                break

            while True:
                screencap = await self.p.screencap()
                crop = screencap.crop(
                    self.config['locations']['confirm_button_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                if text == "CONFIRM":
                    await self.tap("confirm_button")
                    continue
                if text != "CANCEL":
                    print("Cancel button is gone, we ready to move on")
                    break

            print("Sleeping for cutscene")
            await asyncio.sleep(10)

            while True:
                screencap = await self.p.screencap()
                crop = screencap.crop(self.config['locations']['weight_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                if text != "WEIGHT":
                    print("Waiting for pokemon to appear (WEIGHT not found)", text)
                    continue
                crop = screencap.crop(self.config['locations']['height_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                if text != "HEIGHT":
                    print(
                        "Waiting for pokemon to appear (HEIGHT not found", text)
                    continue
                print("Height and weight found, continuing")
                break

            await self.tap("close_pokemon_button")


if __name__ == '__main__':
    if platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    parser = argparse.ArgumentParser(description='Pokemon go renamer')
    parser.add_argument('--device-id', type=str, default=None,
                        help="Optional, if not specified the phone is automatically detected. Useful only if you have multiple phones connected. Use adb devices to get a list of ids.")
    parser.add_argument('--max-retries', type=int, default=0,
                        help="Maximum retries, set to 0 for unlimited.")
    parser.add_argument('--touch-paste', default=False, action='store_true',
                        help="Use touch instead of keyevent for paste.")
    args = parser.parse_args()

    asyncio.run(Main(args).start())
