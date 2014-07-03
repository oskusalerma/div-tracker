#!/usr/bin/env python

import csv
import datetime
from decimal import Decimal
import os

class Object(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def readCsvFile(filename):
    """ Read CSV file, return data as a list of objects with named fields. """

    f = open(filename, "r")
    csvReader = csv.reader(f)

    ret = []
    headers = None

    for row in csvReader:
        # skip empty or commented out rows
        if not row or row[0].startswith("#"):
            continue

        if not headers:
            headers = row
        else:
            assert len(row) == len(headers), "Invalid row in data file: %s" % row

            ret.append(Object(**dict(zip(headers, row))))

    return ret

class DividendEvent(object):
    def __init__(self, data):
        """ data is one of the objects from readCsvFile. """

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
    return Decimal("%.10f" % (float(ev.amount) * 100.0 / ev.shares))

def getDivEvents():
    """ Get all dividend events, sorted by date. """

    data = readCsvFile("%s/info/investing/divs.csv" % os.environ["HOME"])
    events = [DividendEvent(x) for x in data]
    eventsByDate = sorted(events, dateCmp)

    return eventsByDate

if __name__ == "__main__":
    events = getDivEvents()
    print DividendEvent.header()

    for ev in events:
        print ev.asList()
