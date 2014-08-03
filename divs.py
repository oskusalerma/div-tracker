#!/usr/bin/env python

import csv
import datetime
from decimal import Decimal
import os
import os.path

class Object(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def readCsvFile(filename):
    """ Read CSV file, return list of DividendEvents. """

    f = open(filename, "r")
    csvReader = csv.reader(f)

    ret = []
    headers = None

    # it's easy to make mistakes while editing the CSV file. dividends are by
    # their very nature recurring events, so in practise they're always
    # copy/pasted and the date/amount changed. it's far too easy to forget
    # to change the date though, so some built-in error checking comes in handy.
    #
    # dividends should be listed in sections, each section separated by at least
    # one empty line, and within each section, they should be listed in ascending
    # date order.
    startOfSection = True

    for row in csvReader:
        # empty line
        if not row:
            startOfSection = True

            continue

        # comment
        if row[0].startswith("#"):
            continue

        if not headers:
            headers = row
        else:
            assert len(row) == len(headers), "Invalid row in data file: %s" % row

            obj = Object(**dict(zip(headers, row)))
            ev = DividendEvent(obj)

            if not startOfSection:
                assert ev.date >= ret[-1].date, \
                    "Dates within each section must be in ascending order: %s" % row

            startOfSection = False
            ret.append(ev)

    return ret

class DividendEvent(object):
    def __init__(self, data):
        """ data is Object. """

        dt = datetime.datetime.strptime(data.date, "%d.%m.%Y")
        self.date = datetime.date(dt.year, dt.month, dt.day)

        self.person = data.person
        self.broker = data.broker
        self.accountType = data.accountType
        self.company = data.company
        self.shares = int(data.shares)
        self.amount = Decimal(data.amount)

    @staticmethod
    def header():
        return ["date", "person", "broker", "accountType", "company",
                "shares", "amount", "amountPerShare"]

    def asList(self):
        return [self.date, self.person, self.broker, self.accountType,
                self.company, self.shares, self.amount,
                perShareAmountFunc(self)]

def dateCmp(ev1, ev2):
    return cmp(ev1.date, ev2.date)

def nominalAmountFunc(ev):
    return ev.amount

def perShareAmountFunc(ev):
    return Decimal("%.2f" % (float(ev.amount) * 100.0 / ev.shares))

def getDivEvents():
    """ Get all dividend events, sorted by date. """

    filesToTry = [
        "%s/info/investing/divs.csv" % os.environ["HOME"],
        "%s/sample.csv" % os.path.dirname(__file__),
        ]

    events = None

    for filename in filesToTry:
        if os.path.isfile(filename):
            events = readCsvFile(filename)

            break

    if events is None:
        raise Exception("No data files found, tried %s" % filesToTry)

    eventsByDate = sorted(events, dateCmp)

    return eventsByDate

if __name__ == "__main__":
    events = getDivEvents()
    print DividendEvent.header()

    for ev in events:
        print ev.asList()
