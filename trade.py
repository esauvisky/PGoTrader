#!/usr/bin/env python3.7
import argparse
import random
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


def get_center_point(box_coordinates):
    """
    Returns the center point coordinate of a rectangle.

    Args:
        box_coordinates (list): A list of four (int) coordinates,
                                representing a rectangle "box".
    Returns:
        list: A list with two (int) coordinates, the center point
              of the coordinate, i.e.: the intersection between
              the rectangle's diagonals.
    """
    x1, y1, x2, y2 = box_coordinates
    return [int((x1 + x2) / 2), int((y1 + y2) / 2)]


class InvalidTapCoordinates(Exception):
    # TODO: the WIP wizard should probably be dealt here
    pass


class Main:
    def __init__(self, args):
        with open(args.config, "r") as f:
            self.config = yaml.load(f)
        self.args = args
        tools = pyocr.get_available_tools()
        self.tool = tools[0]
        self.p = PokemonGo()
        self.i = 2

        self.CHECK_STRING = self.config['names']['name_check']
        self.SEARCH_STRING = self.config['names']['search_string']

    async def tap(self, location):
        # TODO: this should be moved to pokemonlib?
        try:
            coordinates = self.config['locations'][location]
        except Exception as e:
            logger.error('The location is not yet setup in config.yaml. Either set them up manually, or use the wizard.')
            raise e

        if len(coordinates) == 2:
            await self.p.tap(*coordinates)
        elif len(coordinates) == 4:
            center_point = get_center_point(coordinates)
            await self.p.tap(*center_point)
        else:
            logger.error('Something is not right.')
            raise InvalidTapCoordinates

        if location in self.config['waits']:
            await asyncio.sleep(self.config['waits'][location])

    async def key(self, keycode):
        await self.p.key(keycode)
        if str(keycode).lower in self.config['waits']:
            await asyncio.sleep(self.config['waits'][str(keycode).lower])

    async def switch_app(self):
        logger.info('Switching apps...')
        await self.key('APP_SWITCH')
        await self.tap('second_app_position')

    async def click_trade_button(self, app='second'):
        count = 0
        while True:
            screencap = await self.p.screencap()
            crop = screencap.crop(self.config['locations']['waiting_box'])  #.quantize(random.randint(2,5), kmeans=random.randint(1,4))
            text_wait = self.tool.image_to_string(crop).replace("\n", " ")
            crop = screencap.crop(self.config['locations']['error_box'])  #.quantize(random.randint(2,5), kmeans=random.randint(1,4))
            text_error = self.tool.image_to_string(crop).replace("\n", " ")
            crop = screencap.crop(self.config['locations']['pokemon_to_trade_box'])  #.quantize(2, kmeans=random.randint(1,4))
            text_continue_trade = self.tool.image_to_string(crop).replace("\n", " ")
            crop = screencap.crop(self.config['locations']['trade_button_label'])  #.quantize(2, kmeans=random.randint(1,4))
            text_trade_button = self.tool.image_to_string(crop).replace("\n", " ")

            # Switches apps whenever count is too high (usually fixes stall problems, particularly on 'Waiting for' screen)
            if count > 5:
                count = 0
                logger.error('The trade has stalled. Trying to switch apps...')
                await self.switch_app()
                continue

            if "Trade expired" in text_error:
                logger.info('Found Trade expired box.')
                await self.tap('error_box_ok')
            elif "This trade with" in text_error:
                logger.info('Found This trade with... has expired box.')
                await self.tap('error_box_ok')
            elif "out of range" in text_error:
                logger.info('Found out of range box.')
                await self.tap('error_box_ok')
            elif "Unknown Trade Error" in text_error:
                logger.info('Found Unknown Trade Error box.')
                await self.tap('error_box_ok')
            elif "Waiting for" in text_wait:
                if app == 'first':
                    logger.warning('"Waiting for" message received! Trade is good to go! Continuing...')
                    break
                else:
                    logger.info('"Waiting for" message received! Waiting for POKEMON TO TRADE screen...')
                    count += 1
            elif "POKEMON TO TRADE" in text_continue_trade:
                logger.warning('"POKEMON TO TRADE" message received! Trade is good to go! Continuing...')
                break
            elif "TRADE" in text_trade_button:
                logger.warning('Clicking TRADE button...')
                await self.tap('trade_button')
            else:
                logger.info('Did not find TRADE button. Got: ' + text_trade_button)
                count += 1
                if count >= 6:
                    await self.check_animation_has_finished()

    async def search_select_and_click_next(self):
        while True:
            screencap = await self.p.screencap()
            crop = screencap.crop(self.config['locations']['pokemon_to_trade_box']) #.quantize(2, kmeans=random.randint(1,4))
            text = self.tool.image_to_string(crop).replace("\n", " ")
            if "POKEMON TO TRADE" not in text:
                logger.info('Not in pokemon to trade screen. Trying again...')
            else:
                logger.warning('Found POKEMON TO TRADE screen, selecting pokemons...')
                break

        # Filter pokemon list
        await self.tap("search_button")
        await self.p.send_intent("clipper.set", extra_values=[["text", self.SEARCH_STRING]])
        await self.p.key('KEYCODE_PASTE')
        await self.tap("first_pokemon")  # Dismiss keyboard
        await self.tap("first_pokemon")
        await asyncio.sleep(1.5)

        # Selects and clicks next
        while True:
            screencap = await self.p.screencap()
            crop = screencap.crop(self.config['locations']['next_button_box'])
            text = self.tool.image_to_string(crop).replace("\n", " ")
            if "NEXT" not in text:
                logger.info("Waiting for next, got" + text)
                continue
            logger.warning("Found next button checking name...")
            crop = screencap.crop(self.config['locations']['name_at_next_screen_box']).quantize(random.randint(2,10), kmeans=random.randint(1,4))
            text = self.tool.image_to_string(crop).replace("\n", " ")
            if self.CHECK_STRING not in text:
                logger.error("[Next Screen] Pokemon does not match " + self.CHECK_STRING + ". Got: " + text)
                continue
            logger.warning("Name is good. Clicking next...")
            await self.tap("next_button")
            break

    async def check_and_confirm(self, app='second'):
        count = 0
        while True:
            screencap = await self.p.screencap()
            crop = screencap.crop(self.config['locations']['confirm_button_box']).quantize(random.randint(2,5), kmeans=random.randint(1,4))
            text = self.tool.image_to_string(crop).replace("\n", " ")
            if text != "CONFIRM":
                logger.info("Waiting for confirm, got " + text)
                continue
            logger.warning("Found confirm button, performing last check...")
            crop = screencap.crop(self.config['locations']['trade_name_box']).quantize(self.i, kmeans=random.randint(1,4))
            text = self.tool.image_to_string(crop).replace("\n", " ")
            crop2 = screencap.crop(self.config['locations']['trade_name_box_no_location'])
            text2 = self.tool.image_to_string(crop2).replace("\n", " ")
            if self.CHECK_STRING not in text and self.CHECK_STRING not in text2:
                logger.error("[Confirm Screen] Pokemon name is wrong! I've got: " + text + ' and ' + text2)
                self.i = max(1,self.i + random.randint(-1,2))
                count += 1
                if count > 10:
                    count = 0
                    logger.error("Something's not right... Trying to fix it")
                    await self.tap("error_box_ok")
                    await self.tap("leave_button")
                    await self.tap("error_box_ok")
                continue
            logger.warning("Pokemon name's good, confirming...")
            await self.tap("confirm_button")

            # Add a detect for the CANCEL button, just for the first app
            # when GPS fails exactly at the right moment it doesn't counts
            if app == 'first':
                count = 0
                while True:
                    count += 1
                    logger.warning("Detecting CANCEL...")
                    screencap = await self.p.screencap()
                    crop = screencap.crop(self.config['locations']['confirm_button_box']).quantize(random.randint(2,5), kmeans=random.randint(1,4))
                    text = self.tool.image_to_string(crop).replace("\n", " ")
                    if text != "CANCEL":
                        logger.info("Waiting for cancel, got " + text)
                        count += 1
                        if count > 7:
                            count = 0
                            logger.error('The confirming did not work. Trying again...')
                            await self.tap("error_box_ok")
                            await self.tap("leave_button")
                            await self.tap("error_box_ok")
                        continue
                    logger.warning('Found CANCEL. First app is OK. Moving on...')
                    break
            elif app == 'second':
                await asyncio.sleep(2)
                screencap = await self.p.screencap()
                crop = screencap.crop(self.config['locations']['confirm_button_box']).quantize(random.randint(2,5), kmeans=random.randint(1,4))
                text = self.tool.image_to_string(crop).replace("\n", " ")
                while text == "CONFIRM":
                    logger.error("Confirmation didn't get through. Trying again...")
                    await self.tap("confirm_button")
                    continue
                break
            break

    async def check_animation_has_finished(self):
        count = 0
        while True:
            screencap = await self.p.screencap()
            crop = screencap.crop(self.config['locations']['weight_box']).quantize(random.randint(2,5), kmeans=random.randint(1,4))
            text = self.tool.image_to_string(crop).replace("\n", " ")
            if 'WEIGHT' in text or 'kg' in text:
                logger.warning('Animation finished, closing pokemon and moving on!')
                await self.tap("close_pokemon_button")
                break
            logger.info('Animation not finished yet...')
            count += 1
            if count > 10:
                logger.critical('Something bad happened. :| Trying to fix it.')
                await self.tap("error_box_ok")
                await asyncio.sleep(10)
                await self.tap("close_pokemon_button")
                await asyncio.sleep(10)
                break

    async def start_single(self):
        await self.p.set_device(self.args.device_id)
        count = 0

        while True:
            await self.click_trade_button()

            await self.search_select_and_click_next()

            await self.check_and_confirm()

            logger.warning('Sleeping for cutscene...')
            await asyncio.sleep(16)

            await self.check_animation_has_finished()

            count += 1
            if args.stop_after is not None and count >= args.stop_after:
                logger.info("Stop_after reached, stopping")
                return

    async def start(self):
        await self.p.set_device(self.args.device_id)
        count = 0

        while True:
            await self.click_trade_button('first')
            await self.switch_app()
            await self.click_trade_button()

            await self.search_select_and_click_next()

            await self.switch_app()

            await self.search_select_and_click_next()

            await self.check_and_confirm('first')

            await self.switch_app()

            await self.check_and_confirm()

            logger.warning('Sleeping for cutscene...')
            await asyncio.sleep(16)

            await self.check_animation_has_finished()

            # Switches back. The expired mesage will be clicked on the next loop
            await self.switch_app()

            count += 1
            if args.stop_after is not None and count >= args.stop_after:
                logger.info("Stop_after reached, stopping")
                return


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Pokemon go renamer')
    parser.add_argument('--device-id', type=str, default=None,
                        help="Optional, if not specified the phone is automatically detected. Useful only if you have multiple phones connected. Use adb devices to get a list of ids.")
    parser.add_argument('--config', type=str, default='config.yaml',
                        help="Config file location.")
    parser.add_argument('--stop-after', default=None, type=int,
                        help='Stop after X pokemon')
    args = parser.parse_args()

    asyncio.run(Main(args).start())
