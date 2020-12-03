#!/usr/bin/env python
"""
Basic script to deal with handling repeat bookings at GymBox franchise.
"""
import re
import json
import time
import datetime
from bs4 import BeautifulSoup
import requests
import os

class AutoBooker:
    """ Does what is says... """
    def __init__(self, email, password):
        self.email = email
        self.password = password
        # Set it to 1031 so that it doesn't jump the gun
        self.booking_time = '10:31'
        self.booking_hour = self.booking_time[:2:]
        # 23 hours and 55 mins
        self.wait_a_day = 86100
        self.browser_session = None
        self.gymbox_main = 'https://gymbox.legendonlineservices.co.uk/enterprise/'

    @staticmethod
    def extract_timetable(page_content):
        """ Returns the extracted raw html timetable from the class schedule page """
        html_timetable = None
        for line_values in page_content.splitlines():
            if "Gym Entry Time" in line_values:
                html_timetable = line_values
        return html_timetable

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
        # This is so that you can edit the file between bookings
        json_file.close()

    def book_class(self, class_data):
        """ Completes the booking and closes the browser session """
        booking_url = self.gymbox_main + 'BookingsCentre/AddBooking?booking='
        confirm_booking_url = self.gymbox_main + 'Basket/Pay'
        print(f"BOOKING : {class_data[2]} at {class_data[1]} on {class_data[0]}")
        self.browser_session.get(f'{booking_url}{class_data[3]}')
        self.browser_session.get(confirm_booking_url)
        self.browser_session.close()

    def login_get_timetable(self):
        """ Logs into the members portal and extracts the raw timetable """
        self.browser_session = requests.session()
        login_url = self.gymbox_main + "account/login"
        timetable = self.gymbox_main + 'BookingsCentre/MemberTimetable'

        verification_token = self.browser_session.get(login_url).cookies['__RequestVerificationToken']

        form_data = {'login.Email': self.email,
                     'login.Password': self.password,
                     '__RequestVerificationToken': verification_token}

        page_post = self.browser_session.post(login_url, form_data, allow_redirects=True)
        if "Login failed" in page_post.text:
            raise RuntimeError("Login Failed")
        return self.browser_session.get(timetable).text

    def main(self):
        """ Main running loop, duh """
        while True:
            cur_time = time.strftime('%H:%M')
            if self.booking_time == cur_time:
                raw_timetable = self.login_get_timetable()
                booking_timetable = self.parse_timetable(raw_timetable)
                self.booking_handler(booking_timetable)
                print("BOOKED - Waiting until tomorrow...")
                time.sleep(self.wait_a_day)
            # Waits on the run-up of the booking window
            elif self.booking_hour == time.strftime('%H'):
                print("Almost time to book...")
                time.sleep(10)
            # Captures the initial startup
            else:
                print(f"Waiting until {self.booking_time}...")
                time.sleep(30)


if __name__ == '__main__':
    email = os.environ.get('GYMBOX_EMAIL')
    password = os.environ.get('GYMBOX_PASSWORD')

    if not email or not password:
        print("GYMBOX_EMAIL and GYMBOX_PASSWORD must both be present in the environment.\n"
              "This can be done from the command line with:\n"
              "export GYMBOX_EMAIL=youremail\n"
              "export GYMBOX_PASSWORD=yourpassword\n\n"
              "If you have a .bashrc file or equivalent, you can export them from there, and"
              " won't need to remember to export them for every new terminal session.\n\n"
              "You can also pass them directly when running the script, like so:\n"
              "GYMBOX_EMAIL=youremail GYMBOX_PASSWORD=yourpassword python3 main.py")
        exit(1)

    book_it_plz = AutoBooker(email, password)
    book_it_plz.main()
