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
formatter = ColoredFormatter("  %(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s")
ch.setFormatter(formatter)
logger.addHandler(ch)


TRADE_POKEMON_CHECK = "TRADE"
POKEMON_SEARCH_STRING = "Ω"


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

    async def cap_and_crop(self, box_location):
        '''
        Returns the text from a location after a screencap
        '''
        screencap = await self.p.screencap()
        crop = screencap.crop(box_location)
        text = self.tool.image_to_string(crop).replace("\n", " ")
        logger.info('[OCR] Found text: ' + text)
        return text

    async def switch_app(self):
        logger.info('Switching apps...')
        await self.key('APP_SWITCH')
        await self.tap('second_app_position')

    async def click_trade_button(self):
        while True:
            screencap = await self.p.screencap()
            crop = screencap.crop(self.config['locations']['waiting_box'])
            text_wait = self.tool.image_to_string(crop).replace("\n", " ")
            crop = screencap.crop(self.config['locations']['error_box'])
            text_error = self.tool.image_to_string(crop).replace("\n", " ")
            crop = screencap.crop(self.config['locations']['pokemon_to_trade_box'])
            text_continue_trade = self.tool.image_to_string(crop).replace("\n", " ")
            crop = screencap.crop(self.config['locations']['trade_button_label'])
            text_trade_button = self.tool.image_to_string(crop).replace("\n", " ")
            if "Trade expired" in text_error:
                logger.info('Found Trade expired box.')
                await self.tap('error_box_ok')
                continue
            elif "This trade with" in text_error:
                logger.info('Found This trade with... has expired box.')
                await self.tap('error_box_ok')
                continue
            elif "Unknown trade error" in text_error:
                logger.info('Found This trade with... has expired box.')
                await self.tap('error_box_ok')
                continue
            elif "Waiting for" in text_wait:
                logger.warning('"Waiting for" message received!')
                break
            elif "POKEMON TO TRADE" in text_continue_trade:
                logger.warning('Trade is good to go! Continuing...')
                break
            elif "TRADE" in text_trade_button:
                logger.warning('Found TRADE button, clicking and checking...')
                await self.tap('trade_button')
            else:
                logger.info('Did not find TRADE button. Got: ' + text_trade_button)

    async def search_select_and_click_next(self):
        while True:
            text = await self.cap_and_crop(self.config['locations']['pokemon_to_trade_box'])
            if "POKEMON TO TRADE" not in text:
                logger.info('Not in pokemon to trade screen. Trying again...')
            else:
                logger.warning('Found POKEMON TO TRADE screen, selecting pokemons...')
                break

        # Filter pokemon list
        await self.tap("search_button")
        await self.p.send_intent("clipper.set", extra_values=[["text", POKEMON_SEARCH_STRING]])
        await self.p.key('KEYCODE_PASTE')
        await self.tap("first_pokemon")  # Dismiss keyboard
        await self.tap("first_pokemon")

        # Selects and clicks next
        while True:
            text = await self.cap_and_crop(self.config['locations']['next_button_box'])
            if text != "NEXT":
                logger.info("Waiting for next, got" + text)
                continue
            logger.warning("Found next button")
            text = await self.cap_and_crop(self.config['locations']['name_at_next_screen_box'])
            if TRADE_POKEMON_CHECK not in text:
                logger.error("First pokemon does not match " + TRADE_POKEMON_CHECK + ".")
                continue
            await self.tap("next_button")
            break

    async def check_and_confirm(self):
        while True:
            text = await self.cap_and_crop(self.config['locations']['confirm_button_box'])
            if text != "CONFIRM":
                logger.info("Waiting for confirm, got " + text)
                continue
            logger.warning("Found confirm button, performing last check...")
            text = await self.cap_and_crop(self.config['locations']['trade_name_box'])
            if TRADE_POKEMON_CHECK not in text:
                logger.error("Pokemon name is wrong! I've got: " + text)
                return
            logger.warning("All good, confirming...")
            await self.tap("confirm_button")
            break


    async def start(self):
        self.p = PokemonGo()
        await self.p.set_device(self.args.device_id)

        while True:
            await self.click_trade_button()
            await self.switch_app()
            await self.click_trade_button()

            await self.search_select_and_click_next()

            await self.switch_app()

            await self.search_select_and_click_next()

            await self.check_and_confirm()

            await self.switch_app()

            await self.check_and_confirm()

            # while True:
            #     screencap = await self.p.screencap()
            #     crop = screencap.crop(
            #         self.config['locations']['confirm_button_box'])
            #     text = self.tool.image_to_string(crop).replace("\n", " ")
            #     if text == "CONFIRM":
            #         await self.tap("confirm_button")
            #         continue
            #     if text != "CANCEL":
            #         print("Cancel button is gone, we ready to move on")
            #         break

            # print("Sleeping for cutscene")
            # await asyncio.sleep(10)

            # while True:
            #     screencap = await self.p.screencap()
            #     crop = screencap.crop(self.config['locations']['weight_box'])
            #     text = self.tool.image_to_string(crop).replace("\n", " ")
            #     if text != "WEIGHT":
            #         print("Waiting for pokemon to appear (WEIGHT not found)", text)
            #         continue
            #     crop = screencap.crop(self.config['locations']['height_box'])
            #     text = self.tool.image_to_string(crop).replace("\n", " ")
            #     if text != "HEIGHT":
            #         print(
            #             "Waiting for pokemon to appear (HEIGHT not found", text)
            #         continue
            #     print("Height and weight found, continuing")
            #     break

            # await self.tap("close_pokemon_button")

            # # Switches and clicks the expired message
            # await self.key('APP_SWITCH')
            # await self.tap('second_app_position')

            # while True:
            #     crop = screencap.crop(self.config['locations']['error_box'])
            #     text = self.tool.image_to_string(crop).replace("\n", " ")
            #     if "Trade expired" in text:
            #         print('Found Trade expired box.')
            #         await self.tap('error_box_ok')
            #         break
            #     elif "This trade with" in text:
            #         print('Found This trade with... has expired box.')
            #         await self.tap('error_box_ok')
            #         break



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
