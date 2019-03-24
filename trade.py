#!/usr/bin/env python3.7
import argparse
import asyncio
import cv2
import numpy
import logging
import re
import sys
from sys import platform

import yaml
from PIL import Image
from pyocr import builders, pyocr

from pokemonlib import PokemonGo

try:
    import colorlog
    HAVE_COLORLOG = True
except ImportError:
    HAVE_COLORLOG = False


def create_logger():
    '''Setup the logging environment'''
    log = logging.getLogger()  # root logger
    log.setLevel(logging.INFO)
    format_str = '[%(asctime)s] (%(name)8.8s) %(levelname)8s | %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    if HAVE_COLORLOG:
        cformat = '%(log_color)s' + format_str
        formatter = colorlog.ColoredFormatter(cformat, date_format)
    else:
        formatter = logging.Formatter(format_str, date_format)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    log.addHandler(stream_handler)
    return logging.getLogger(__name__)

def get_median_location(box_location):
    '''
    Given a list of 4 coordinates, returns the central point of the box
    '''
    x1, y1, x2, y2 = box_location
    return [int((x1 + x2) / 2), int((y1 + y2) / 2)]


class Main:
    def __init__(self, args):
        with open(args.config, "r") as f:
            self.config = yaml.load(f)
        self.args = args
        tools = pyocr.get_available_tools()
        self.tool = tools[0]
        self.p = PokemonGo()

        self.CHECK_STRING = self.config['names']['name_check']
        self.SEARCH_STRING = self.config['names']['search_string']

    async def pick_box_coordinate(self, image):
        # Read image
        try:
            img = cv2.cvtColor(numpy.array(image), cv2.COLOR_RGB2BGR)
        except AttributeError:
            img = cv2.imread(image)
        except TypeError:
            img = cv2.imread(image.filename)
        except Exception as e:
            logger.error(e)
            exit()

        height, width, _ = img.shape

        # Select ROI
        cv2.namedWindow("Select", cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_EXPANDED)
        cv2.resizeWindow("Select", (int(width/2), int(height/2)))
        r = cv2.selectROI("Select", img)

        # Crop image
        imCrop = img[int(r[1]):int(r[1] + r[3]), int(r[0]):int(r[0] + r[2])]

        if imCrop.size == 0:
            return False

        # Display cropped image
        # cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
        # cv2.imshow("Image", imCrop)
        key = cv2.waitKey(0)
        if key == 13:
            cv2.destroyAllWindows()



        logging.critical('You picked [%s, %s, %s, %s]', int(r[0]), int(r[1]), int(r[0] + r[2]), int(r[1] + r[3]))
        return [int(r[0]), int(r[1]), int(r[0] + r[2]), int(r[1] + r[3])]


    async def tap(self, location):
        while True:
            try:
                coordinates = self.config['locations'][location]
            except Exception as e:
                print(e)

            if coordinates == None:
                new_location = await self.get_location(location)
                coordinates = self.config['locations'][location] = new_location
                continue

            break


        if len(coordinates) == 2:
            await self.p.tap(*coordinates)
            if location in self.config['waits']:
                await asyncio.sleep(self.config['waits'][location])
        elif len(coordinates) == 4:
            median_location = get_median_location(coordinates)
            await self.p.tap(*median_location)
            if location in self.config['waits']:
                await asyncio.sleep(self.config['waits'][location])
        else:
            logger.error('Something is not right.')
            raise Exception

    async def key(self, keycode):
        await self.p.key(keycode)
        if str(keycode).lower in self.config['waits']:
            await asyncio.sleep(self.config['waits'][str(keycode).lower])

    async def switch_app(self):
        logger.info('Switching apps...')
        await self.key('APP_SWITCH')
        await asyncio.sleep(1)
        await self.tap('second_app_position')

    async def get_text(self, image, location):
        '''OCR's a piece/box of an image and returns the string, if any.add()

        Arguments:
            image    {image}   -- image object
            location {string}  -- the name of the location in config.yaml

        Returns:
            [string|bool] -- Returns the OCR'd text, or false if empty or nothing found.
        '''

        while True:
            try:
                cropped_image = image.crop(self.config['locations'][location])
            except:
                final_string = None
            else:
                final_string = self.tool.image_to_string(cropped_image).replace("\n", " ").strip()

            if not self.config['locations'][location]:
                new_location = await self.get_location(location)
                self.config['locations'][location] = new_location
                cropped_image = image.crop(new_location)
                continue

            if location == 'confirm_button_box' and "CONFIRM" not in final_string:
                logger.error('Apparently your selection did not worked out. This button is always tricky. Try to select a different sized rectangle until it works')
                continue

            break


        return final_string

    async def get_location(self, location):
        '''Checks if the location exists on yaml.
            In case it doesn't, opens the wizard to pick coords.
            Afterwards appends them it on picked_coordinates.txt.

        Arguments:
            location {string} -- the name of the location
            image    {image}  -- an image file or image object

        Returns:
            [array]           -- an array of either two or four elements
        '''
        logger.critical('Coordinate not found! Please select the coordinates for %s and press Space or Enter twice when done.', location)

        while True:
            image = await self.p.screencap()
            try:
                coordinates = await self.pick_box_coordinate(image)
            except ValueError:
                continue
            else:
                if not coordinates:
                    continue
                break

        with open("picked_coordinates.txt", mode="a") as file:
            file.write(str(location) + ': ' + str(coordinates) + '\n')
        logger.warning('Coordinate was saved to file picked_coordinates.txt. Put them on config.yaml afterwards to avoid this problem!')
        return coordinates


    async def click_trade_button(self, app='second'):
        count = 0
        while True:
            screencap = await self.p.screencap()
            text_wait = await self.get_text(screencap, 'waiting_box')
            text_error = await self.get_text(screencap, 'error_box')
            text_continue_trade = await self.get_text(screencap, 'pokemon_to_trade_box')
            text_trade_button = await self.get_text(screencap, 'trade_button_label')

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
                await self.tap('trade_button_label')
            else:
                logger.info('Did not find TRADE button. Got: ' + text_trade_button)

    async def search_select_and_click_next(self):
        while True:
            screencap = await self.p.screencap()
            text = await self.get_text(screencap, 'pokemon_to_trade_box')
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
            text = await self.get_text(screencap, 'next_button_box')
            if text != "NEXT":
                logger.info("Waiting for next, got" + text)
                continue
            logger.warning("Found next button checking name...")
            text = await self.get_text(screencap, 'name_at_next_screen_box')
            if self.CHECK_STRING not in text:
                logger.error("[Next Screen] Pokemon does not match " + self.CHECK_STRING + ". Got: " + text)
                continue
            logger.warning("Name is good. Clicking next...")
            await self.tap("next_button_box")
            break

    async def check_and_confirm(self, app='second'):
        while True:
            screencap = await self.p.screencap()
            text = await self.get_text(screencap, 'confirm_button_box')
            if text != "CONFIRM":
                logger.info("Waiting for confirm, got " + text)
                continue
            logger.warning("Found confirm button, performing last check...")
            text = await self.get_text(screencap, 'trade_name_box')
            text2 = await self.get_text(screencap, 'trade_name_box_no_location')
            if self.CHECK_STRING not in text and self.CHECK_STRING not in text2:
                logger.error("[Confirm Screen] Pokemon name is wrong! I've got: " + text + ' and ' + text2)
                continue
            logger.warning("Pokemon name's good, confirming...")
            await self.tap("confirm_button_box")

            # Add a detect for the CANCEL button, just for the first app
            # when GPS fails exactly at the right moment it doesn't counts
            if app == 'first':
                count = 0
                while True:
                    count += 1
                    logger.warning("Detecting CANCEL...")
                    screencap = await self.p.screencap()
                    text = await self.get_text(screencap, 'confirm_button_box')
                    if text != "CANCEL":
                        logger.info("Waiting for cancel, got " + text)
                        if count > 5:
                            count = 0
                            logger.error('The confirming did not work. Trying again...')
                            await self.tap("confirm_button_box")
                        continue
                    logger.warning('Found CANCEL. First app is OK. Moving on...')
                    break
            elif app == 'second':
                await asyncio.sleep(2)
                screencap = await self.p.screencap()
                text = await self.get_text(screencap, 'confirm_button_box')
                while text == "CONFIRM":
                    logger.error("Confirmation didn't get through. Trying again...")
                    await self.tap("confirm_button_box")
                    continue
                break
            break

    async def check_animation_has_finished(self):
        while True:
            screencap = await self.p.screencap()
            text = await self.get_text(screencap, 'weight_box')
            if 'WEIGHT' in text or 'kg' in text:
                logger.warning('Animation finished, closing pokemon and moving on!')
                await self.tap("close_pokemon_button")
                break
            logger.info('Animation not finished yet...')

    async def start(self):
        await self.p.set_device(self.args.device_id)

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


if __name__ == '__main__':
    logger = create_logger()
    parser = argparse.ArgumentParser(description='Pokemon go renamer')
    parser.add_argument('--device-id', type=str, default=None,
                        help="Optional, if not specified the phone is automatically detected. Useful only if you have multiple phones connected. Use adb devices to get a list of ids.")
    parser.add_argument('--config', type=str, default='config.yaml',
                        help="Config file location.")
    args = parser.parse_args()

    asyncio.run(Main(args).start())
