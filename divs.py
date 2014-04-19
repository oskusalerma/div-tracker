import csv
import datetime
from decimal import Decimal

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
        if not headers:
            headers = row
        else:
            assert len(row) == len(headers)

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

    data = readCsvFile("/home/osku/info/investing/divs.csv")
    events = [DividendEvent(x) for x in data]
    eventsByDate = sorted(events, dateCmp)

    return eventsByDate
