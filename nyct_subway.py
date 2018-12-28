#!/usr/bin/python
# encoding: utf-8

import csv
import re
from StringIO import StringIO
import sys
from workflow import Workflow3, web, ICON_ERROR, ICON_INFO


BOROUGH = {"M": "Manhattan", "Bk": "Brooklyn", "Q": "Queens", "Bx": "The Bronx", "SI": "Staten Island"}


# Get subway time
def get_time(wf, complex_routes, gtfs_stop_id_complex, route, gtfs_stop_id):
    # Find all transferrable services in the current complex
    complex_id = gtfs_stop_id_complex[gtfs_stop_id.encode("ascii", "ignore")]
    subtitle = ""
    if complex_routes.get(complex_id) is not None and len(complex_routes[complex_id]) > 1:
        transfer_routes = sorted(list(complex_routes[complex_id]))
        subtitle = "Transfer is available to the %s trains" % ", ".join(transfer_routes)
    # Get subway time by service and station
    response = web.get("http://traintimelb-367443097.us-east-1.elb.amazonaws.com/getTime/%s/%s" % (route, gtfs_stop_id))
    response.raise_for_status()
    station = response.json()
    station_name = station["stationName"]
    wf.add_item(title=u"%s" % station_name, subtitle=u"%s" % subtitle, icon="images/MTA.png")
    directions = [None] * 2
    directions[0] = station["direction1"]
    directions[1] = station["direction2"]
    for direction in directions:
        if len(direction["times"]) != 0:  # Some station has only one direction
            for time in direction["times"]:
                if time["lastStation"] != station_name:  # Show non-terminal only
                    subtitle = ""
                    if direction["name"]:  # Show the name of direction if not empty
                        if direction["name"] in ["Uptown", "Downtown"]:
                            subtitle = direction["name"]
                        else:
                            subtitle = direction["name"] + " bound"
                    broadcast_suffix = ""  # Mimic the station broadcasting
                    if isinstance(time["minutes"], (int, long)):
                        minutes = "%d minutes" % time["minutes"] if time["minutes"] > 1 else "%d minute" % time["minutes"]
                        broadcast_suffix = minutes + " away" if time["minutes"] > 0 else " approaching the station"
                    else:
                        minutes = broadcast_suffix = time["minutes"]
                    wf.add_item(
                        title=u"To %s: %s" % (time["lastStation"], minutes),
                        subtitle=u"%s" % subtitle,
                        valid=True,
                        arg=u"There is a(n) %s %s train to %s %s" % (subtitle, time["route"], time["lastStation"], broadcast_suffix),
                        icon="images/%s.png" % time["route"]
                        )


# Get all stations
def get_station_list():
    response = web.get("http://web.mta.info/developers/data/nyct/subway/Stations.csv")
    response.raise_for_status()
    f = StringIO(response.text)
    stations = []  # All stations
    complex_routes = {}  # All complexes
    gtfs_stop_id_complex = {}  # Stop ID - complex ID
    for row in csv.DictReader(f, skipinitialspace=True):
        station = {}
        for key, value in row.items():
            if key == "Station ID" or key == "Complex ID":
                station[key] = int(value)
            elif key == "Daytime Routes":
                station[key] = value.split()
            else:
                station[key] = value
        stations.append(station)
        if complex_routes.get(station["Complex ID"]) is None:
            complex_routes[station["Complex ID"]] = set(station["Daytime Routes"])
        else:
            complex_routes[station["Complex ID"]] |= set(station["Daytime Routes"])
        gtfs_stop_id_complex[station["GTFS Stop ID"]] = station["Complex ID"]
    return stations, complex_routes, gtfs_stop_id_complex


def get_stations(wf, stations, query):
    outputs = []
    for station in stations:
        if query.lower() in station["Stop Name"].lower():
            outputs.append(station)
    # Add to the lists of results for Alfred
    if len(outputs) == 0:
        wf.add_item(title=u"Error", subtitle=u"Station \"%s\" does not exist" % query, icon=ICON_ERROR)
    else:
        wf.add_item(title=u"Instruction", subtitle=u"Select a station and press Tab key to see the subway time", icon=ICON_INFO)
        for station in outputs:
            for route in station["Daytime Routes"]:
                wf.add_item(
                    title=u"%s" % station["Stop Name"],
                    subtitle=u"%s - %s" % (BOROUGH[station["Borough"]], " ".join(station["Daytime Routes"])),
                    icon="images/%s.png" % route,
                    autocomplete="%s@%s" % (route, station["GTFS Stop ID"])
                    )


def main(wf):
    stations, complex_routes, gtfs_stop_id_complex = wf.cached_data("nyct_subway_all_stations", get_station_list, max_age=60 * 60 * 24)
    query = " ".join(wf.args).split("@")
    if len(query) == 2 and re.match("^[A-Z0-9]$|^SIR$", query[0]) and re.match("^[A-Z0-9][0-9]{2}$", query[1]):  # Get time for the station
        get_time(wf, complex_routes, gtfs_stop_id_complex, query[0], query[1])
    else:  # Search stations
        get_stations(wf, stations, query[0])
    wf.send_feedback()


if __name__ == "__main__":
    wf = Workflow3(update_settings={
        "github_slug": "maobowen/nyct-subway-alfred-workflow",
        "frequency": 7
        })
    if wf.update_available:
        wf.add_item(
            title=u"New version available",
            subtitle=u"Action this item to install the update",
            autocomplete="workflow:update",
            icon=ICON_INFO
            )
    sys.exit(wf.run(main))
