import requests
from bs4 import BeautifulSoup
import re
import lxml.html
import json
import time
import datetime


class AutoBooker:
    def __init__(self):
        self.login_details = {"login.Email": "user@email.com",
                              "login.Password": "password"}
        # Set it to 1031 so that it doesn't jump the gun
        self.BOOKING_TIME = '10:31'
        self.BOOKING_HOUR = self.BOOKING_TIME[:2:]
        # 23 hours and 55 mins
        self.WAIT_A_DAY = 86100

    def strip_token(self, raw_page_data):
        token_array = []
        for nLines in raw_page_data.splitlines():
            if '__RequestVerificationToken' in nLines:
                token_to_strip = nLines
                token_array.append(nLines.split("value=\"")[1][:92:])
        return token_array

    def generate_token(self, data_array):
        token_value = data_array[1]
        token_name = '__RequestVerificationToken'
        return {token_name: token_value}

    def extract_timetable(self, page_content):
        html_timetable = ''
        for nLines in page_content.splitlines():
            if "Gym Entry Time" in nLines:
                html_timetable = nLines
        return html_timetable

    # make this return a timetable with date, time, booking ID
    def parse_timetable(self, raw_timetable):
        souper = BeautifulSoup(raw_timetable, 'html.parser')
        parsed_table = souper.find_all('table')
        gym_time = parsed_table[1]
        class_name = ''
        time_slot = ''
        date = ''
        class_booking_code = ''
        complete_timetable = []
        for tr in gym_time:
            table_row = tr.find_all('td')
            first_col = re.split('[><]', str(table_row[0]))
            # '''
            # Time slots
            if len(first_col) == 13:
                time_slot = first_col[4]
            # Date
            elif len(first_col) == 11:
                date = first_col[6][2::]
            # '''
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
        json_file = open('classes_config.json')
        my_classes = json.load(json_file)

        seven_days = datetime.timedelta(days=7)
        future_date = (datetime.datetime.today() + seven_days).strftime('%d %B %Y')
        future_day_name = datetime.datetime.today().strftime('%A')

        for timetable_entry in timetable_data:
            if future_day_name in my_classes:
                if list(my_classes[future_day_name].keys())[0] == timetable_entry[2]:
                    if my_classes[future_day_name][list(my_classes[future_day_name].keys())[0]] == timetable_entry[1]:
                        if future_date in timetable_entry[0]:
                            self.book_class(timetable_entry)
        # This is so that you can edit the file between bookings
        json_file.close()

    def book_class(self, class_data):
        # Below is how the site makes bookings
        booking_url = 'https://gymbox.legendonlineservices.co.uk/enterprise/BookingsCentre/AddBooking?booking='
        confirm_booking_url = 'https://gymbox.legendonlineservices.co.uk/enterprise/Basket/Pay'
        print(f"BOOKING : {class_data[2]} at {class_data[1]} on {class_data[0]}")
        self.browser_session.get(f'{booking_url}{class_data[3]}')
        self.browser_session.get(confirm_booking_url)
        self.browser_session.close()

    def login_get_timetable(self):
        self.browser_session = requests.session()
        login_url = "https://gymbox.legendonlineservices.co.uk/enterprise/account/login"
        timetable = 'https://gymbox.legendonlineservices.co.uk/enterprise/BookingsCentre/MemberTimetable'
        page_get = self.browser_session.get(login_url)
        verification_token = self.generate_token(self.strip_token(page_get.text))
        self.login_details.update(verification_token)
        page_post = self.browser_session.post(login_url, self.login_details, allow_redirects=True)
        if "Login failed" in page_post.text:
            print("Login Failed")
            raise RuntimeError
        return self.browser_session.get(timetable).text

    def main(self):
        # Check/wait loop
        while True:
            cur_time = time.strftime('%H:%M')
            if self.BOOKING_TIME == cur_time:
                raw_timetable = self.login_get_timetable()
                booking_timetable = self.parse_timetable(raw_timetable)
                self.booking_handler(booking_timetable)
                print("BOOKED - Waiting until tomorrow...")
                time.sleep(self.WAIT_A_DAY)
            # Waits on the run-up of the booking window
            elif self.BOOKING_HOUR == time.strftime('%H'):
                print("Almost time to book...")
                time.sleep(10)
            # Captures the initial startup
            else:
                print(f"Waiting until {self.BOOKING_TIME}...")
                time.sleep(30)


if __name__ == '__main__':
    book_it_plz = AutoBooker()
    book_it_plz.main()
