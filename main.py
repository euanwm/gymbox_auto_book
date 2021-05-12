#!/usr/bin/env python
"""
Gymbox has an excellent booking system however due to Gymbox not policing no-shows
the open gym time slots are fully booked but with a poor turnout. I wrote this code
to automate it for me sometime last year and made it public because fuck Gymbox.

Put it on a Raspberry Pi, put in the time you want into the classes_config, run it. Done.

I am not good at writing code.
"""

import re
import json
import time
import datetime
from bs4 import BeautifulSoup
import requests


class AutoBooker:
    """ Does what is says... """
    def __init__(self):
        self.LOGIN_DETAILS = {"login.Email": "email@email.com",
                              "login.Password": "password"}
        # It was 10:31 before everyone started to set their alarms
        self.BOOKING_TIME = '10:30'
        self.BOOKING_HOUR = self.BOOKING_TIME[:2:]
        # 23 hours and 55 mins
        self.WAIT_A_DAY = 86100
        self.MAX_RETRIES = 5
        # Seconds to wait before re-attempting a booking
        self.WAIT_RETRY = 2
        self.GYMBOX_URL = 'https://gymbox.legendonlineservices.co.uk/enterprise/'
        self.LOGIN_URL = self.GYMBOX_URL + "account/login"
        self.TIMETABLE_URL = self.GYMBOX_URL + 'BookingsCentre/MemberTimetable'
        self.CONFIRM_BOOKING_URL = self.GYMBOX_URL + '/Basket/Pay'
        self.BOOKING_URL = self.GYMBOX_URL + 'BookingsCentre/AddBooking?booking='
        self.BROWSER_SESSION = None

    @staticmethod
    def extract_token(login_response):
        """ Checks GET response header, returns the verification token to allow a secure login """
        return {'__RequestVerificationToken': login_response.cookies['__RequestVerificationToken']}

    @staticmethod
    def extract_timetable(page_content):
        """ Returns the extracted raw html timetable from the class schedule page """
        html_timetable = None
        for line_values in page_content.splitlines():
            if "Gym Entry Time" in line_values:
                html_timetable = line_values
        return html_timetable

    @staticmethod
    def save_timetable(parsed_timetable):
        """ Passes the results of the parsed timetable into a txt file """
        current_time_date = time.strftime("%d%m%Y_%H%M")
        filename = f"timetable_{current_time_date}.txt"
        # Added for debugging shite
        timetable_file = open(filename, "w")
        for tt_entries in parsed_timetable:
            timetable_file.write(f"{tt_entries}\n")

    # make this return a timetable with date, time, booking ID
    @staticmethod
    def parse_timetable(raw_timetable):
        """ Takes raw html timetable and converts into an array """
        souper = BeautifulSoup(raw_timetable, 'html.parser')
        parsed_table = souper.find_all('table')
        gym_time = parsed_table[1]
        class_name = ''
        time_slot = ''
        date = ''
        class_booking_code = ''
        complete_timetable = []
        for table_row in gym_time:
            table_row = table_row.find_all('td')
            first_col = re.split('[><]', str(table_row[0]))
            # Time slots
            if len(first_col) == 13:
                time_slot = first_col[4]
            # Date
            elif len(first_col) == 11:
                date = first_col[6][2::]
            if len(table_row) > 1:
                second_col = re.split('[><]', str(table_row[1]))
                third_col = re.split('[><]', str(table_row[6]))
                if len(second_col) > 5:
                    class_name = second_col[6]
                if len(third_col) == 9:
                    class_booking_code = third_col[3].split("slot")[1][:7:]
            if date and time_slot and class_name and class_booking_code:
                array_to_insert = [date, time_slot, class_name, class_booking_code]
                complete_timetable.append(array_to_insert)
        return complete_timetable

    def booking_handler(self, timetable_data):
        """ Checks timetable data against the classes marked for booking and makes the booking """
        json_file = open('classes_config.json')
        my_classes = json.load(json_file)

        seven_days = datetime.timedelta(days=7)
        future_date = (datetime.datetime.today() + seven_days).strftime('%d %B %Y')
        future_day_name = datetime.datetime.today().strftime('%A')

        # ToDo: Refactor to reduce line length
        for timetable_entry in timetable_data:
            if future_day_name in my_classes:
                if list(my_classes[future_day_name].keys())[0] == timetable_entry[2]:
                    if my_classes[future_day_name][list(my_classes[future_day_name].keys())[0]] == timetable_entry[1]:
                        if future_date in timetable_entry[0]:
                            self.book_class(timetable_entry)
        # Close the file after reading so you can keep the script running and make amendments
        json_file.close()

    def book_class(self, class_data):
        """ Takes the class ID then attempts to book it up to a maximum of attempts """
        for attempt in range(self.MAX_RETRIES):
            print(f"BOOKING ATTEMPT {attempt + 1} : {class_data[2]} \
             ({class_data[3]}) at {class_data[1]} on {class_data[0]}")
            self.BROWSER_SESSION.get(f'{self.BOOKING_URL}{class_data[3]}')
            print("Added to basket...")
            checkout_page = self.BROWSER_SESSION.get(self.CONFIRM_BOOKING_URL)
            print("Checked out...")
            if "Your booking is now complete." in checkout_page.text:
                print("Class booked successfully.")
                break
            else:
                print("CLASS NOT BOOKED")
                failed_page = open("failed_booking.html", "w")
                failed_page.write(checkout_page.text)
                failed_page.close()
                time.sleep(self.WAIT_RETRY)
        self.BROWSER_SESSION.close()

    def login_get_timetable(self):
        """ Logs into the members portal and extracts the raw timetable """
        self.BROWSER_SESSION = requests.session()
        page_get = self.BROWSER_SESSION.get(self.LOGIN_URL)
        verification_token = self.extract_token(page_get)
        self.LOGIN_DETAILS.update(verification_token)
        page_post = self.BROWSER_SESSION.post(self.LOGIN_URL, self.LOGIN_DETAILS, allow_redirects=True)
        if "Login failed" in page_post.text:
            print("Login Failed")
            raise RuntimeError
        return self.BROWSER_SESSION.get(self.TIMETABLE_URL).text

    def main(self):
        """ Main running loop """
        print("### Autobooker started...")
        # Check/wait loop
        while True:
            # ToDo: Calculate sleep time until the next applicable booking window
            cur_time = time.strftime('%H:%M')
            cur_time_secs = time.strftime('%H:%M:%S')
            if self.BOOKING_TIME == cur_time:
                print(f"Initiated booking at {cur_time_secs}")
                raw_timetable = self.login_get_timetable()
                booking_timetable = self.parse_timetable(raw_timetable)
                self.save_timetable(booking_timetable)
                self.booking_handler(booking_timetable)
                time.sleep(self.WAIT_A_DAY)
            # Waits on the run-up of the booking window
            elif self.BOOKING_HOUR == time.strftime('%H'):
                time.sleep(10)
            # Captures the initial startup
            else:
                time.sleep(5)

    def debug(self):
        """ Skips out the timing/scheduling loop """
        raw_timetable = self.login_get_timetable()
        booking_timetable = self.parse_timetable(raw_timetable)
        self.save_timetable(booking_timetable)

if __name__ == '__main__':
    book_it_plz = AutoBooker()
    #book_it_plz.debug()
    book_it_plz.main()
