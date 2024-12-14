import yaml
import random
import base64
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from apiclient import errors

class Person:
    """Object containing details of each person on Santa's list"""
    def __init__(self, name, contact=None):
        self.name = name
        self.contact = contact
        self.exclusions = []  # Persons not to match with
        self.naughty = False
        self.nice = True

    def __str__(self):
        return "{:s}".format(self.name)

    def __repr__(self):
        return self.__str__()

    def add_exclusion(self, person):
        self.exclusions.append(person)

def make_dict_of_persons(names, contacts=None, exclusions=None, exclude_both_ways=True):
    """Given a list of names and optionally a list of contact addresses (e.g. emails)
    create a dict containing a Person object for each name.
    If a list of exclusions are supplied, add these to the objects.
    It is assumed exclusions are two-way. If they are only intended to be one-way, this can be toggled."""

    # Create dict to contain person objects
    persons = {}

    # Go through lists and append persons to list
    for idx in range(len(names)):
        name = names[idx]
        # If contacts are provided, include these
        if contacts:
            contact = contacts[idx]
        else:
            contact = None
        persons[name] = Person(name, contact)

    # If exclusions provided, add these to the persons
    if exclusions:
        for excluded_pair in exclusions:
            persons[excluded_pair[0]].add_exclusion(persons[excluded_pair[1]])
            if exclude_both_ways:
                persons[excluded_pair[1]].add_exclusion(persons[excluded_pair[0]])

    return persons

class Gift:
    """Object containing the pairs of giver-receiver on Santa's list."""
    def __init__(self, giver, reciever):
        self.giver = giver
        self.reciever = reciever

    def __str__(self):
        return "{:s} ==> {:s}".format(self.giver.name, self.reciever.name)

    def __repr__(self):
        return self.__str__()

class Santa:
    """Santa takes a dict of person objects, containing their name, contact, and any exclusions.
    He makes a list, matching up gifters and receivers ensuring validity.
    He checks it twice.
    He can also find out who is naughty or nice."""
    def __init__(self, persons):
        self.persons = persons
        self.list = []

        self.max_num_attempts = 100
        self.num_attempts = 0

    def __str__(self):
        if self.list:
            return "Santa has assigned gifts to the {:d} people on his list".format(len(self.persons))
        else:
            return "Santa has {:d} people on his list".format(len(self.persons))

    def __repr__(self):
        return self.__str__()

    def select_pair(self, giver, recievers):
        """Given a giver and a list of available receivers,
        assign a receiver giver's gift.
        Check its validity, if it's invalid try again.
        If the pairing is invalid and one receiver is left the pairing is not possible,
        and the list needs to be made again"""
        reciever = random.choice(recievers)
        if self.check_pair_valid(giver, reciever):
            return Gift(self.persons[giver], self.persons[reciever])
        else:
            if len(recievers) == 1:
                raise RecursionError('Invalid selection made, one invalid receiver left. Try again.')
            return self.select_pair(giver, recievers)  # Infinite recursion possible without above check

    def check_pair_valid(self, giver, reciever):
        """Check a pair of giver / receiver is valid
        Potential invalidity may come from:
         - Giver is receiver
         - Receiver is on giver's exclusion list
        Returns True/False"""
        if self.persons[giver] == self.persons[reciever]:
            return False
        if self.persons[reciever] in self.persons[giver].exclusions:
            return False
        else:
            return True

    def check_list_valid(self, gifts=None):
        """Check the validity of an input gift list or the self.list
        Potential invalidity may come from:
         - Empty list
         - Someone gifting to themselves
         - Someone gifting to someone on their exclusion list
        Returns True/False"""

        if not gifts:
            gifts = self.list

        if len(gifts) < 1:
            raise ValueError('Empty gift list')

        for gift in gifts:
            if gift.giver == gift.reciever:
                print('Invalid combination: {:s} giving to themselves'.format(gift.giver.name))
                return False
            if gift.reciever in gift.giver.exclusions:
                print('Invalid combination: {:s} in exclusion list of {:s}'.format(gift.reciever.name, gift.giver.name))
                return False
        return True

    def make_a_single_list(self):
        """Go through the list of givers
        Picking a gift recipient for each
        Sometimes this may give a RecursionError
        Due to the random.choice giving an invalid selection
        This is handled in self.make_a_list"""
        gifts = []
        givers = list(self.persons)
        recievers = list(self.persons)
        for giver in givers:
            gift = self.select_pair(giver, recievers)
            gifts.append(gift)
            recievers.remove(gift.reciever.name)
        return gifts

    def make_a_list(self):
        """Sometimes the random.choice ends up leaving an invalid selection
        Make several attempts at choosing a valid selection
        Up to the self.max_num_attempts"""
        self.num_attempts = 0
        while self.num_attempts <= self.max_num_attempts:
            self.num_attempts += 1
            try:
                gifts = self.make_a_single_list()
                if self.check_list_valid(gifts):
                    self.list = gifts
                    return self.list
            except RecursionError:  # Invalid selection remaining, try again
                continue
        raise ValueError('Unable to find valid combination after {:d} attempts. Decrease number of exclusions or increase max_num_attempts.'.format(self.max_num_attempts))

    def display(self):
        print('Assigned gifts:')
        print(*self.list, sep='\n')

    def who_is_naughty(self):
        naughty_list = [person for person in self.persons.values() if person.naughty]
        print("Santa has {:d} people on his naughty list".format(len(naughty_list)))
        print(*naughty_list, sep='\n')

    def who_is_nice(self):
        nice_list = [person for person in self.persons.values() if person.nice]
        print("Santa has {:d} people on his nice list".format(len(nice_list)))
        print(*nice_list, sep='\n')

class Elves:
    """Santa's elves take his list and the dict of persons and
    informs each gifter of their secret santa pairing"""
    def __init__(self, persons, gifts, message):
        self.persons = persons
        self.gifts = gifts
        self.message = message

        self.valid = self.check_list_valid()
        self.contactable = self.check_contactable()

    def check_list_valid(self, gifts=None):
        """Santa's elves perform their own check that Santa's list is valid
        Potential invalidity may come from:
         - Empty list
         - Someone gifting to themselves
         - Someone gifting to someone on their exclusion list
        Returns True/False"""

        if not gifts:
            gifts = self.gifts

        if len(gifts) < 1:
            raise ValueError('Empty gift list')

        for gift in self.gifts:
            if gift.giver == gift.reciever:
                print('Invalid combination: {:s} giving to themselves'.format(gift.giver.name))
                return False
            if gift.reciever in gift.giver.exclusions:
                print('Invalid combination: {:s} in exclusion list of {:s}'.format(gift.reciever.name, gift.giver.name))
                return False
        return True

    def check_contactable(self, persons=None):
        """Check everyone on the persons list has a contact address"""

        if not persons:
            persons = self.persons

        if len(persons) < 1:
            raise ValueError('Empty persons list')

        for person in persons.values():
            if not person.contact:
                return False
        return True

    def generate_email_message(self, giver_name, reciever_name):
        return self.message.format(name=giver_name, gift_reciever=reciever_name)

    def send_email(self):
        if not self.valid:
            raise ValueError('Gift list is not valid')
        if not self.contactable:
            raise ValueError('Not every participant has an email address')

        # If modifying these scopes, delete the file token.json.
        SCOPES = ['https://www.googleapis.com/auth/gmail.send']
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=8080)
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        service = build('gmail', 'v1', credentials=creds)

        # Preview message
        print('\nPREVIEW OF MESSAGE:\n========\n' + self.message + '\n========\n')

        # Confirm addresses to send to
        list_of_email_recipients = [f"{person.name} <{person.contact}>" for person in self.persons.values()]
        print('\nTHIS MESSAGE WILL BE FORMATTED AND SENT TO:')
        print(*list_of_email_recipients, sep='\n')

        if input('\nProceed? [y/n]: ') != 'y':
            print('Emails not sent.')
            return

        for gift in self.gifts:
            giver_email = gift.giver.contact
            message_body = self.generate_email_message(gift.giver.name, gift.reciever.name)
            email_message = f"To: {giver_email}\nSubject: {subject}\n\n{message_body}"
            message = {
                'raw': base64.urlsafe_b64encode(email_message.encode("utf-8")).decode("utf-8")
            }
            try:
                message = (service.users().messages().send(userId="me", body=message).execute())
                print(f'E-mail sent successfully to {giver_email}')
            except errors.HttpError as error:
                print(f'An error occurred: {error}')

        print(f'{len(self.gifts)} emails sent. Merry Christmas!')

def main():
    # Load YAML file
    with open('secretsanta.yml', 'r') as yaml_file:
        data = yaml.load(yaml_file, Loader=yaml.BaseLoader)

    # Parse YAML file
    names = []
    contacts = []
    for name in data['NAMES']:
        if ',' in name:
            split_name = name.split(',')
            names.append(split_name[0].strip())
            contacts.append(split_name[1].strip())
    exclusions = []
    for pair in data['EXCLUDE']:
        if ',' in pair:
            split_exclusion = pair.split(',')
            split_exclusion = [ex.strip() for ex in split_exclusion]
            exclusions.append(split_exclusion)
    exclude_both_ways = data['EXCLUDE_BOTH_WAYS'].lower() in ['true', 'yes']
    global message
    message = data['MESSAGE']
    global subject
    subject = data['SUBJECT']
    message = "Subject:{subject}\n\n{message}".format(subject=subject, message=message)
    send = data['SEND'].lower() in ['true', 'yes']
    display = data['DISPLAY_RESULT'].lower() in ['true', 'yes']
    seed = data.get('RNG_SEED')

    # Make the list
    persons = make_dict_of_persons(names, contacts, exclusions, exclude_both_ways=exclude_both_ways)
    santa = Santa(persons)
    if seed:
        random.seed(seed)
    gifts = santa.make_a_list()

    if display:
        print('Secret santa assignments:')
        print(*gifts, sep='\n')

    if send:
        # Send it via email using Gmail API
        elves = Elves(persons, gifts, message)
        elves.send_email()

if __name__ == "__main__":
    main()
