import collections
import csv
import datetime
from decimal import Decimal

from flask import Flask, request, url_for, make_response

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

MONTH_APRIL_NEXT = "April (next)"

BUCKET_H_YEAR = "year"
BUCKET_H_TAX_YEAR = "taxYear"

ACCOUNT_TYPE_NORMAL = "Normal"
ACCOUNT_TYPE_ISA = "ISA"

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

def dateCmp(ev1, ev2):
    return cmp(ev1.date, ev2.date)

def taxYearOfDate(date):
    """ Return UK tax year of given date. Examples:

    5.4.2013 -> 2012
    6.4.2013 -> 2013
    """

    if date.month < 4:
        return date.year - 1
    elif date.month > 4:
        return date.year
    else:
        # UK tax year begins on April 6
        if date.day >= 6:
            return date.year
        else:
            return date.year - 1

def filterBy(events, attrName, attrVals):
    return [x for x in events if getattr(x, attrName) in attrVals]

def getDivEvents():
    """ Get all dividend events, sorted by date. """

    data = readCsvFile("/home/osku/info/investing/divs.csv")
    events = [DividendEvent(x) for x in data]
    eventsByDate = sorted(events, dateCmp)

    return eventsByDate

def groupBy(
    events, bucketsH, bucketHFunc, bucketsV, bucketVFunc, amountFunc, titleV):
    def defVal():
        return collections.defaultdict(Decimal)

    # key = bucketH value, value = dict where key is bucketV value, value =
    # sum of dividends in that month
    data = collections.defaultdict(defVal)

    for ev in events:
        data[bucketHFunc(ev)][bucketVFunc(ev)] += amountFunc(ev)

    ret = [[titleV] + bucketsH]

    for bucketV in bucketsV:
        val = [bucketV]

        for bucketH in bucketsH:
            val.append(data[bucketH][bucketV])

        ret.append(val)

    ret.append(
        ["Total"] +
        [sum(data[bucketH].values()) for bucketH in bucketsH])

    return ret

def nominalAmountFunc(ev):
    return ev.amount

def perShareAmountFunc(ev):
    return Decimal("%.10f" % (float(ev.amount) / ev.shares))

def byYear(events, amountFunc):
    def hFunc(ev):
        return "%d" % ev.date.year

    # TODO: this breaks if we have a gap in yearly payments, like for BP;
    # should really iterate over years instead manually
    bucketsH = sorted(list(set(hFunc(ev) for ev in events)))

    bucketsV = MONTHS

    def vFunc(ev):
        return MONTHS[ev.date.month - 1]

    return groupBy(
        events,
        bucketsH, hFunc,
        bucketsV, vFunc,
        amountFunc,
        "Month",
        )

def byTaxYear(events, amountFunc):
    def hFunc(ev):
        taxYear = taxYearOfDate(ev.date)
        return "%d-%d" % (taxYear, taxYear + 1)

    # TODO: this breaks if we have a gap in yearly payments, like for BP;
    # should really iterate over years instead manually
    bucketsH = sorted(list(set(hFunc(ev) for ev in events)))

    bucketsV = MONTHS[3:] + MONTHS[:3] + [MONTH_APRIL_NEXT]

    def vFunc(ev):
        # UK tax year begins on April 6
        if not ((ev.date.month == 4) and (ev.date.day < 6)):
            return MONTHS[ev.date.month - 1]
        else:
            return MONTH_APRIL_NEXT

    return groupBy(
        events,
        bucketsH, hFunc,
        bucketsV, vFunc,
        amountFunc,
        "Month",
        )

def renderTable(data):
    res = []

    res.append("<table cellspacing=1 cellpadding=3 bgcolor=white>")

    for i in range(len(data)):
        row = data[i]

        if i == 0:
            name = "th"
            color = "#dfdfdf"
        else:
            name = "td"

            if (i % 2) == 0:
                color = "#FFE1C6"
            else:
                color = "#FFCFA4"

        s = "<tr bgcolor=%s>" % color

        for it in row:
            if isinstance(it, (float, Decimal)):
                val = "%.2f" % float(it)
            else:
                val = str(it)

            s += " <%s>%s</%s>" % (name, val, name)

        s += "</tr>"

        res.append(s)

    res.append("</table>")

    return "\n".join(res)

app = Flask(__name__)

@app.route("/")
def main():
    allEvents = getDivEvents()
    events = allEvents

    company = request.args.get("company")
    if company:
        events = filterBy(events, "company", [company])

    person = request.args.get("person")
    if person:
        events = filterBy(events, "person", [person])

    broker = request.args.get("broker")
    if broker:
        events = filterBy(events, "broker", [broker])

    accountType = request.args.get("accountType")
    if accountType:
        if accountType in [ACCOUNT_TYPE_ISA, ACCOUNT_TYPE_NORMAL]:
            events = filterBy(events, "accountType", [accountType])
        else:
            raise Exception("Unknown accountType %s" % accountType)

    perShare = request.args.get("perShare")
    if perShare == "1":
        amountFunc = perShareAmountFunc
    else:
        amountFunc = nominalAmountFunc

    bucketH = request.args.get("bucketH", BUCKET_H_YEAR)

    if bucketH == BUCKET_H_YEAR:
        res = byYear(events, amountFunc)
    elif bucketH == BUCKET_H_TAX_YEAR:
        res = byTaxYear(events, amountFunc)
    else:
        raise Exception("Unknown bucketH: %s" % bucketH)

    if request.args.get('csv') == "1":
        s = []
        for row in res:
            s.append(",".join([str(x) for x in row]))

        csvData = "\n".join(s)
        response = make_response(csvData)
        response.headers["Content-Type"] = "text/csv"
        response.headers["Content-Disposition"] = "attachment;filename=data.csv"
        return response

    tbl = renderTable(res)

    links = []
    indent = "&nbsp;&nbsp;"

    params = {
        "accountType" : accountType,
        "broker" : broker,
        "bucketH" : bucketH,
        "company" : company,
        "perShare" : perShare,
        "person" : person,
        }

    def makeLink(key, val, text):
        if params.get(key) == val:
            return "%s<b>%s</b>" % (indent, text)
        else:
            d = dict(params)
            d[key] = val
            return "%s<a href=\"%s\">%s</a>" % (indent, url_for("main", **d), text)

    with app.test_request_context():
        links.append("<a href=\"%s\">Home</a>" % url_for("main"))

        links.append("")
        links.append("Year")
        links.append(makeLink("bucketH", BUCKET_H_YEAR, "Calendar"))
        links.append(makeLink("bucketH", BUCKET_H_TAX_YEAR, "Tax year"))

        links.append("")
        links.append("Account type")
        links.append(makeLink("accountType", None, "All"))
        links.append(makeLink("accountType", ACCOUNT_TYPE_NORMAL, "Normal"))
        links.append(makeLink("accountType", ACCOUNT_TYPE_ISA, "ISA"))

        links.append("")
        links.append("Person")
        links.append(makeLink("person", None, "All"))

        for p in sorted(set((ev.person for ev in allEvents))):
            links.append(makeLink("person", p, p))

        links.append("")
        links.append("Broker")
        links.append(makeLink("broker", None, "All"))

        for p in sorted(set((ev.broker for ev in allEvents))):
            links.append(makeLink("broker", p, p))

        links.append("")
        links.append("Amount")
        links.append(makeLink("perShare", None, "Nominal"))
        links.append(makeLink("perShare", "1", "Per share"))

        links.append("")
        links.append("Company")
        links.append(makeLink("company", None, "All"))

        for c in sorted(set((ev.company for ev in allEvents))):
            links.append(makeLink("company", c, c))


    header = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>

<head>
<link rel=stylesheet type="text/css" href="%s">
</head>

<body>
""" % url_for("static", filename = "style.css")

    sidebar = "<div id=sidebar>\n%s\n</div>" % "\n<br>".join(links)
    main = "<div id=main>\n%s\n%s\n</div>" % (
        tbl,
        makeLink("csv", "1", "<img src=\"%s\">" % url_for("static", filename = "excel.jpg")))

    footer = """
</body>
</html>
"""
    return "\n\n".join([header, sidebar, main, footer])

if __name__ == "__main__":
    app.run(debug = True)
