from decimal import Decimal
import collections
import datetime
import urllib

from django.contrib.staticfiles.templatetags.staticfiles import static
from django.urls import reverse
from django.http import HttpResponse
from django.shortcuts import render

import divs

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

MONTH_APRIL_NEXT = "April (next)"

BUCKET_H_YEAR = "year"
BUCKET_H_TAX_YEAR = "taxYear"

ACCOUNT_TYPE_NORMAL = "Normal"
ACCOUNT_TYPE_ISA = "ISA"

CELL_CONTENT_DETAILS = "details"

def url_for(name, **kwargs):
    url = reverse(name)

    if kwargs:
        d = dict(((key, val) for (key, val) in kwargs.iteritems() if val is not None))
        url += "?%s" % urllib.urlencode(d)

    return url

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

def applyRequestFilters(req, events):
    params = {}

    for name in ["company", "person", "broker", "accountType", "isProjected"]:
        val = req.GET.get(name)

        if val:
            events = filterBy(events, name, [val])
            params[name] = val

    return (events, params)

def groupBy(
        req, events, bucketsH, bucketHFunc, bucketsV, bucketVFunc, amountFunc, titleV):
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
            if req.GET.get("cellContent") == CELL_CONTENT_DETAILS:
                val.append(cellContents[bucketH][bucketV])
            else:
                val.append(data[bucketH][bucketV])

        ret.append(val)

    ret.append(
        ["Total"] +
        [sum(data[bucketH].values()) for bucketH in bucketsH])

    return ret

def byYear(req, events, params, amountFunc):
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
        [url_for("main:div-events", **params)] +
        [url_for("main:div-events", year = year, **params) for year in bucketsH])

    for month in bucketsV:
        links.append(
            [url_for("main:div-events", month = month, **params)] +
            [url_for("main:div-events", month = month, year = year, **params) for year in bucketsH])

    # header and footer row have the same links
    links.append(links[0])

    data = groupBy(
        req, events,
        bucketsH, hFunc,
        bucketsV, vFunc,
        amountFunc,
        "Month",
        )

    return (data, links)

def byTaxYear(req, events, params, amountFunc):
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

    # TODO: create links

    data = groupBy(
        req, events,
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

    response = HttpResponse(content_type = "text/csv")
    response["Content-Disposition"] = "attachment;filename=data.csv"
    response.write(csvData)

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
<!DOCTYPE html>
<html>

<head>
<link rel=stylesheet type="text/css" href="%s">
</head>

<body>
""" % static("style.css")

def getHTMLFooter():
    return """
</body>
</html>
"""

def formatLink(linkUrl, text):
    return "<a href=\"%s\">%s</a>" % (linkUrl, text)

def home(req):
    today = datetime.date.today()
    allEvents = divs.getDivEvents()
    lastDivs = divs.getLastDivEventsByCompany(allEvents)
    events, params = applyRequestFilters(req, allEvents)

    perShare = req.GET.get("perShare")
    if perShare == "1":
        amountFunc = divs.perShareAmountFunc
    else:
        amountFunc = divs.nominalAmountFunc

    bucketH = req.GET.get("bucketH", BUCKET_H_YEAR)

    if bucketH == BUCKET_H_YEAR:
        res, resLinks = byYear(req, events, params, amountFunc)
    elif bucketH == BUCKET_H_TAX_YEAR:
        res, resLinks = byTaxYear(req, events, params, amountFunc)
    else:
        raise Exception("Unknown bucketH: %s" % bucketH)

    if req.GET.get("csv") == "1":
        return renderCsv(res)

    tbl = renderTable(res, resLinks)

    links = []
    indent = "&nbsp;&nbsp;"

    # TODO: check if it's worth the hassle of keeping params separate from
    # req.GET
    params["bucketH"] = bucketH
    params["perShare"] = perShare
    params["cellContent"] = req.GET.get("cellContent")

    def makeLink(key, val, text):
        if params.get(key) == val:
            return "%s%s<b>%s</b>" % (indent, indent, text)
        else:
            d = dict(params)
            d[key] = val
            return "%s%s%s" % (indent, indent, formatLink(url_for("main:home", **d), text))

    links.append("<a href=\"%s\">Home</a>" % url_for("main:home"))

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
    links.append("%sStatus" % indent)
    links.append(makeLink("isProjected", None, "All"))
    links.append(makeLink("isProjected", "0", "Realized"))
    links.append(makeLink("isProjected", "1", "Projected"))

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
    links.append("")

    links.append("%s%s<i>Active</i>" % (indent, indent))

    nonActiveCompanies = []
    for c in sorted(set((ev.company for ev in allEvents))):
        if (today - lastDivs[c]).days < 365:
            links.append(makeLink("company", c, c))
        else:
            nonActiveCompanies.append(c)

    links.append("")
    links.append("%s%s<i>Not active</i>" % (indent, indent))

    for c in nonActiveCompanies:
        links.append(makeLink("company", c, c))

    sidebar = "<div id=sidebar>\n%s\n</div>" % "\n<br>".join(links)
    main = "<div id=main>\n%s\n%s\n</div>" % (
        tbl,
        makeLink("csv", "1", "<img src=\"%s\">" % static("excel.jpg")))

    return HttpResponse("\n\n".join([getHTMLHeader(), sidebar, main, getHTMLFooter()]))

def divEvents(req):
    allEvents = divs.getDivEvents()
    events, params = applyRequestFilters(req, allEvents)

    year = int(req.GET.get("year", 0))
    if year:
        events = [ev for ev in events if ev.date.year == year]

    taxYear = int(req.GET.get("taxYear", 0))
    if taxYear:
        events = [ev for ev in events if taxYearOfDate(ev.date) == taxYear]

    month = req.GET.get("month")
    if month:
        events = [ev for ev in events if MONTHS[ev.date.month - 1] == month]

    if req.GET.get("taxYearMonth"):
        # TODO: impl; treats "April" >= day6, "April (next)" < day 6
        raise Exception("taxYearMonth not implemented yet!")

    res = [divs.DividendEvent.header()]
    res.extend([ev.asList() for ev in events])

    if req.GET.get("csv") == "1":
        return renderCsv(res)

    if req.GET:
        filtersStr = ",".join(
            ("%s=%s" % (key, val) for key,val in req.GET.iteritems()))
    else:
        filtersStr = "None"

    filtersStr = "<p>Filters: %s</p>" % filtersStr

    tbl = renderTable(res)

    links = []
    links.append("<a href=\"%s\">Home</a>" % url_for("main:home"))

    d = req.GET.dict()
    d["csv"] = "1"

    csvLink = formatLink(
        url_for("main:div-events", **d),
        "<img src=\"%s\">" % static("excel.jpg"))

    sidebar = "<div id=sidebar>\n%s\n</div>" % "\n<br>".join(links)
    main = "<div id=main>\n%s\n%s\n%s\n\n</div>" % (filtersStr, tbl, csvLink)

    return HttpResponse("\n\n".join([getHTMLHeader(), sidebar, main, getHTMLFooter()]))
