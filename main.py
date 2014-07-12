import collections
from decimal import Decimal

from flask import Flask, request, url_for, make_response

import divs

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

MONTH_APRIL_NEXT = "April (next)"

BUCKET_H_YEAR = "year"
BUCKET_H_TAX_YEAR = "taxYear"

ACCOUNT_TYPE_NORMAL = "Normal"
ACCOUNT_TYPE_ISA = "ISA"

CELL_CONTENT_DETAILS = "details"

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

def applyRequestFilters(events):
    params = {}

    for name in ["company", "person", "broker", "accountType"]:
        val = request.args.get(name)

        if val:
            events = filterBy(events, name, [val])
            params[name] = val

    return (events, params)

def groupBy(
    events, bucketsH, bucketHFunc, bucketsV, bucketVFunc, amountFunc, titleV):
    def defVal():
        return collections.defaultdict(Decimal)

    # key = bucketH value, value = dict where key is bucketV value, value =
    # sum of dividends in that month
    data = collections.defaultdict(defVal)

    def defValStr():
        return collections.defaultdict(str)

    # key = bucketH value, value = dict where key is bucketV value, value =
    # cell contents for that cell (string)
    cellContents = collections.defaultdict(defValStr)

    for ev in events:
        bucketH = bucketHFunc(ev)
        bucketV = bucketVFunc(ev)

        data[bucketH][bucketV] += amountFunc(ev)

        cellContents[bucketH][bucketV] += "%s %s<br>" % (ev.company, amountFunc(ev))

    ret = [[titleV] + bucketsH]

    for bucketV in bucketsV:
        val = [bucketV]

        for bucketH in bucketsH:
            if request.args.get("cellContent") == CELL_CONTENT_DETAILS:
                val.append(cellContents[bucketH][bucketV])
            else:
                val.append(data[bucketH][bucketV])

        ret.append(val)

    ret.append(
        ["Total"] +
        [sum(data[bucketH].values()) for bucketH in bucketsH])

    return ret

def byYear(events, params, amountFunc):
    def hFunc(ev):
        return "%d" % ev.date.year

    # TODO: this breaks if we have a gap in yearly payments, like for BP;
    # should really iterate over years instead manually
    bucketsH = sorted(list(set(hFunc(ev) for ev in events)))

    bucketsV = MONTHS

    def vFunc(ev):
        return MONTHS[ev.date.month - 1]

    links = []
    links.append(
        [url_for("divEvents", **params)] +
        [url_for("divEvents", year = year, **params) for year in bucketsH])

    for month in bucketsV:
        links.append(
            [url_for("divEvents", month = month, **params)] +
            [url_for("divEvents", month = month, year = year, **params) for year in bucketsH])

    # header and footer row have the same links
    links.append(links[0])

    data = groupBy(
        events,
        bucketsH, hFunc,
        bucketsV, vFunc,
        amountFunc,
        "Month",
        )

    return (data, links)

def byTaxYear(events, params, amountFunc):
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

    # FIXME: create links

    data = groupBy(
        events,
        bucketsH, hFunc,
        bucketsV, vFunc,
        amountFunc,
        "Month",
        )

    return (data, None)

def renderCsv(data):
    """ Format data (a list of lists (first list: column names, second:
    items)) as csv and return a response object for said csv data. """

    s = []
    for row in data:
        s.append(",".join([str(x) for x in row]))

    csvData = "\n".join(s)

    response = make_response(csvData)
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = "attachment;filename=data.csv"

    return response

def renderTable(data, links = None):
    """ data is a list of lists (first list: column names, second: items)
    to be rendered into an HTML table. links, if specified, must also be a
    list of lists of exactly the same size as data, but containing URLs
    for links to be used as targets for the cells in the table. a link can
    be None which means no link will be generated for that cell."""

    res = []

    res.append("<table cellspacing=1 cellpadding=3 bgcolor=white>")

    for i, row in enumerate(data):
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

        for j, it in enumerate(row):
            if isinstance(it, (float, Decimal)):
                val = "%.2f" % float(it)
            else:
                val = str(it)

            if links:
                link = links[i][j]

                if link:
                    val = "<a href=\"%s\">%s</a>" % (link, val)

            s += " <%s>%s</%s>" % (name, val, name)

        s += "</tr>"

        res.append(s)

    res.append("</table>")

    return "\n".join(res)

def getHTMLHeader():
    return """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>

<head>
<link rel=stylesheet type="text/css" href="%s">
</head>

<body>
""" % url_for("static", filename = "style.css")

def getHTMLFooter():
    return """
</body>
</html>
"""

def formatLink(linkUrl, text):
    return "<a href=\"%s\">%s</a>" % (linkUrl, text)

app = Flask(__name__)

@app.route("/")
def main():
    allEvents = divs.getDivEvents()
    events, params = applyRequestFilters(allEvents)

    perShare = request.args.get("perShare")
    if perShare == "1":
        amountFunc = divs.perShareAmountFunc
    else:
        amountFunc = divs.nominalAmountFunc

    bucketH = request.args.get("bucketH", BUCKET_H_YEAR)

    if bucketH == BUCKET_H_YEAR:
        res, resLinks = byYear(events, params, amountFunc)
    elif bucketH == BUCKET_H_TAX_YEAR:
        res, resLinks = byTaxYear(events, params, amountFunc)
    else:
        raise Exception("Unknown bucketH: %s" % bucketH)

    if request.args.get("csv") == "1":
        return renderCsv(res)

    tbl = renderTable(res, resLinks)

    links = []
    indent = "&nbsp;&nbsp;"

    # TODO: check if it's worth the hassle of keeping params separate from
    # request.args
    params["bucketH"] = bucketH
    params["perShare"] = perShare
    params["cellContent"] = request.args.get("cellContent")

    def makeLink(key, val, text):
        if params.get(key) == val:
            return "%s%s<b>%s</b>" % (indent, indent, text)
        else:
            d = dict(params)
            d[key] = val
            return "%s%s%s" % (indent, indent, formatLink(url_for("main", **d), text))

    with app.test_request_context():
        links.append("<a href=\"%s\">Home</a>" % url_for("main"))

        links.append("")
        links.append("Grouping")

        links.append("")
        links.append("%sYear" % indent)
        links.append(makeLink("bucketH", BUCKET_H_YEAR, "Calendar"))
        links.append(makeLink("bucketH", BUCKET_H_TAX_YEAR, "Tax year"))

        links.append("")
        links.append("Display")

        links.append("")
        links.append("%sAmount" % indent)
        links.append(makeLink("perShare", None, "Nominal"))
        links.append(makeLink("perShare", "1", "Per share"))

        links.append("")
        links.append("%sCell content" % indent)
        links.append(makeLink("cellContent", None, "Sum"))
        links.append(makeLink("cellContent", CELL_CONTENT_DETAILS, "Details"))

        links.append("")
        links.append("Filters")

        links.append("")
        links.append("%sAccount type" % indent)
        links.append(makeLink("accountType", None, "All"))
        links.append(makeLink("accountType", ACCOUNT_TYPE_NORMAL, "Normal"))
        links.append(makeLink("accountType", ACCOUNT_TYPE_ISA, "ISA"))

        links.append("")
        links.append("%sPerson" % indent)
        links.append(makeLink("person", None, "All"))

        for p in sorted(set((ev.person for ev in allEvents))):
            links.append(makeLink("person", p, p))

        links.append("")
        links.append("%sBroker" % indent)
        links.append(makeLink("broker", None, "All"))

        for p in sorted(set((ev.broker for ev in allEvents))):
            links.append(makeLink("broker", p, p))

        links.append("")
        links.append("%sCompany" % indent)
        links.append(makeLink("company", None, "All"))

        for c in sorted(set((ev.company for ev in allEvents))):
            links.append(makeLink("company", c, c))

    sidebar = "<div id=sidebar>\n%s\n</div>" % "\n<br>".join(links)
    main = "<div id=main>\n%s\n%s\n</div>" % (
        tbl,
        makeLink("csv", "1", "<img src=\"%s\">" % url_for("static", filename = "excel.jpg")))

    return "\n\n".join([getHTMLHeader(), sidebar, main, getHTMLFooter()])

@app.route("/div-events")
def divEvents():
    allEvents = divs.getDivEvents()
    events, params = applyRequestFilters(allEvents)

    year = int(request.args.get("year", 0))
    if year:
        events = [ev for ev in events if ev.date.year == year]

    taxYear = int(request.args.get("taxYear", 0))
    if taxYear:
        events = [ev for ev in events if taxYearOfDate(ev.date) == taxYear]

    month = request.args.get("month")
    if month:
        events = [ev for ev in events if MONTHS[ev.date.month - 1] == month]

    if request.args.get("taxYearMonth"):
        # FIXME: impl; treats "April" >= day6, "April (next)" < day 6
        raise Exception("taxYearMonth not implemented yet!")

    res = [divs.DividendEvent.header()]
    res.extend([ev.asList() for ev in events])

    if request.args.get("csv") == "1":
        return renderCsv(res)

    if request.args:
        filtersStr = ",".join(
            ("%s=%s" % (key, val) for key,val in request.args.iteritems()))
    else:
        filtersStr = "None"

    filtersStr = "<p>Filters: %s</p>" % filtersStr

    tbl = renderTable(res)

    links = []
    links.append("<a href=\"%s\">Home</a>" % url_for("main"))

    d = dict(request.args)
    d["csv"] = "1"

    csvLink = formatLink(
        url_for("divEvents", **d),
        "<img src=\"%s\">" % url_for("static", filename = "excel.jpg"))

    sidebar = "<div id=sidebar>\n%s\n</div>" % "\n<br>".join(links)
    main = "<div id=main>\n%s\n%s\n%s\n\n</div>" % (filtersStr, tbl, csvLink)

    return "\n\n".join([getHTMLHeader(), sidebar, main, getHTMLFooter()])

if __name__ == "__main__":
    app.run(debug = True)
