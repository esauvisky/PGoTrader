import argparse
import asyncio
import logging
import re
from sys import platform

from PIL import Image
import sys
from pyocr import pyocr
from pyocr import builders
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

RE_WAITING_TRADE = re.compile("^Waiting for (.+) to be available for trading.$")
POKEMON_TO_TRADE = "POKEMON TO TRADE"


TRADE_POKEMON_CHECK = "AAA"
TRADE_POKEMON_SEARCH = "∞"


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

    async def key(self, keycode):
        await self.p.key(keycode)
        if str(keycode).lower in self.config['waits']:
            await asyncio.sleep(self.config['waits'][str(keycode).lower])

    # async def swipe(self, location, duration):
    #     await self.p.swipe(
    #         self.config['locations'][location][0],
    #         self.config['locations'][location][1],
    #         self.config['locations'][location][0],
    #         self.config['locations'][location][1],
    #         duration
    #     )
    #     if location in self.config['waits']:
    #         await asyncio.sleep(self.config['waits'][location])

    async def start(self):
        self.p = PokemonGo()
        await self.p.set_device(self.args.device_id)
        # await self.p.start_logcat()

        while True:
            # Wait for trade to start
            await self.tap('trade_button')
            while True:
                screencap = await self.p.screencap()
                crop = screencap.crop(self.config['locations']['waiting_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                match = RE_WAITING_TRADE.match(text)
                if match:
                    print(text)
                    break
                else:
                    crop = screencap.crop(
                        self.config['locations']['pokemon_to_trade_box'])
                    text = self.tool.image_to_string(crop).replace("\n", " ")
                    if text == "POKEMON TO TRADE":
                        print("Pokemon to trade screen reached")
                        break

            # Switch apps
            await self.key('APP_SWITCH')
            await self.tap('second_app_position')

            # Wait for trade to start
            await self.tap('trade_button')
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
            # await self.p.text(TRADE_POKEMON_STRING)
            await self.p.send_intent("clipper.set", extra_values=[["text", TRADE_POKEMON_SEARCH]])
            # await self.p.send_intent('adb shell am broadcast - a clipper.set - e text {}'.format(TRADE_POKEMON_STRING)
            if args.touch_paste:
                await self.swipe('edit_box', 600)
                await self.tap('paste')
            else:
                await self.p.key('KEYCODE_PASTE')
            await asyncio.sleep(1)


            while True:  # Check a pokemon is available and has the correct name
                screencap = await self.p.screencap()
                crop = screencap.crop(
                    self.config['locations']['first_pokemon_name_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                if TRADE_POKEMON_CHECK in text:
                    break
                print("Pokemon name is incorrect, got {}".format(text))

            await self.tap("first_pokemon")  # Dismiss keyboard
            await self.tap("first_pokemon")  # Dismiss keyboard

            # Selects and clicks next
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
                if TRADE_POKEMON_CHECK not in text:
                    print("Pokemons name is wrong, got", text)
                    continue
                await self.tap("next_button")
                break

            # Switches back and selects pkm
            await self.key('APP_SWITCH')
            await self.tap('second_app_position')

            # Wait for trade to start
            await self.tap('trade_button')
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
            # await self.p.text(TRADE_POKEMON_STRING)
            await self.p.send_intent("clipper.set", extra_values=[["text", TRADE_POKEMON_SEARCH]])
            # await self.p.send_intent('adb shell am broadcast - a clipper.set - e text {}'.format(TRADE_POKEMON_STRING)
            if args.touch_paste:
                await self.swipe('edit_box', 600)
                await self.tap('paste')
            else:
                await self.p.key('KEYCODE_PASTE')
            await asyncio.sleep(1)

            while True:  # Check a pokemon is available and has the correct name
                screencap = await self.p.screencap()
                crop = screencap.crop(
                    self.config['locations']['first_pokemon_name_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                if TRADE_POKEMON_CHECK in text:
                    break
                print("Pokemon name is incorrect, got {}".format(text))

            await self.tap("first_pokemon")  # Dismiss keyboard
            await self.tap("first_pokemon")  # Dismiss keyboard

            # Selects and clicks next
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
                if TRADE_POKEMON_CHECK not in text:
                    print("Pokemons name is wrong, got", text)
                    continue
                await self.tap("next_button")
                break

            # Confirms on user 2
            while True:
                screencap = await self.p.screencap()
                crop = screencap.crop(
                    self.config['locations']['confirm_button_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                if text != "CONFIRM":
                    print("Waiting for confirm, got", text)
                    continue
                print("Found confirm button")

                # crop = screencap.crop(self.config['locations']['stardust_box'])
                # text = self.tool.image_to_string(crop).replace("\n", " ")
                # if text >= "800":
                #     print("Expecting less than 800 stardust cost, got", text)
                #     return
                crop = screencap.crop(
                    self.config['locations']['trade_name_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")

                if TRADE_POKEMON_CHECK not in text:
                    print("Pokemon name is wrong, I've got: ", text)
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

            # Switches again, and confirms
            await self.key('APP_SWITCH')
            await self.tap('second_app_position')

            # Confirms on user 1
            while True:
                screencap = await self.p.screencap()
                crop = screencap.crop(
                    self.config['locations']['confirm_button_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                if text != "CONFIRM":
                    print("Waiting for confirm, got", text)
                    continue
                print("Found confirm button")

                # crop = screencap.crop(self.config['locations']['stardust_box'])
                # text = self.tool.image_to_string(crop).replace("\n", " ")
                # if text >= "800":
                #     print("Expecting less than 800 stardust cost, got", text)
                #     return
                crop = screencap.crop(
                    self.config['locations']['trade_name_box'])
                text = self.tool.image_to_string(crop).replace("\n", " ")
                crop = screencap.crop(
                    self.config['locations']['trade_name_box_alt'])
                text2 = self.tool.image_to_string(crop).replace("\n", " ")
                if TRADE_POKEMON_CHECK not in text:
                    print("Pokemon name is wrong, I've got: ", text)
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
    parser = argparse.ArgumentParser(description='Pokemon go renamer')
    parser.add_argument('--device-id', type=str, default=None,
                        help="Optional, if not specified the phone is automatically detected. Useful only if you have multiple phones connected. Use adb devices to get a list of ids.")
    parser.add_argument('--max-retries', type=int, default=0,
                        help="Maximum retries, set to 0 for unlimited.")
    parser.add_argument('--touch-paste', default=False, action='store_true',
                        help="Use touch instead of keyevent for paste.")
    parser.add_argument('--config', type=str, default='config_trades.yaml',
                        help="Config file location.")
    args = parser.parse_args()

    asyncio.run(Main(args).start())
