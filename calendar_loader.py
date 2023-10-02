#!/usr/bin/env python3
import requests, icalendar, argparse, datetime, time, json, hashlib, sys, os

def currenttz():
    if time.daylight:
        return datetime.timezone(datetime.timedelta(seconds=-time.altzone),time.tzname[1])
    else:
        return datetime.timezone(datetime.timedelta(seconds=-time.timezone),time.tzname[0])

dateformat = '%Y-%m-%d'
timeformat = '%Y-%m-%d %H:%M:%S %z'

class CalendarCache(object):
    def __init__(self, url, cache_dir=None, cache_expiry=None):
        self.url = url
        self.cache_dir = cache_dir
        if cache_expiry is None:
            cache_expiry = datetime.timedelta(hours=1)
        self.cache_expiry = cache_expiry
        self.cache_file = '{}.json'.format(hashlib.sha256(url.encode()).hexdigest())

    def get(self):
        if self.cache_dir is not None:
            return self.__get_cache_enabled()
        return self.__retrieve_url_data()
        
    ## Perform the logic of checking the cache (using self.cache_dir)
    def __get_cache_enabled(self):
        now = datetime.datetime.now(currenttz())
        file_data = {'last_update':now.strftime(timeformat), 'data':None}
        file_path = os.path.join(self.cache_dir, self.cache_file)
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'r') as infil:
                    file_data = json.load(infil)
            except:
                ## If we can't load it, oh well, just re-cache it
                pass
        cache_last_update = datetime.datetime.strptime(file_data.get('last_update', '1990-01-01 01:00:00 +0000'), timeformat)
        if file_data['data'] is None or cache_last_update <= (now - self.cache_expiry):
            file_data['data'] = self.__retrieve_url_data()
            file_data['last_update'] = now.strftime(timeformat)
            with open(file_path, 'w') as outfil:
                json.dump(file_data, outfil)
        return file_data['data']

    ## Unconditionally retrieve the data from the expected URL
    def __retrieve_url_data(self):
        calendar_response = requests.get(self.url)
        if calendar_response.status_code != 200:
            calendar_response.raise_for_status()
        return calendar_response.text

class ICalendarCacheWrapper(object):
    def __init__(self, url, cache_dir=None, cache_expiry=None):
        self.calendar_cache = CalendarCache(url, cache_dir=cache_dir, cache_expiry=cache_expiry)

    def get_events(self):
        calendar = icalendar.Calendar.from_ical(self.calendar_cache.get())
        return [ICalendarEvent(event) for event in calendar.walk('VEVENT')]

    def get_events_after(self, dateOrDatetime):
        calendar = icalendar.Calendar.from_ical(self.calendar_cache.get())
        events = []
        for event in calendar.walk('VEVENT'):
            ievent = ICalendarEvent(event)
            relevant = ( ievent.getStart().isoformat() >= dateOrDatetime.isoformat()
                         or ievent.getEnd().isoformat() >= dateOrDatetime.isoformat() )
            if relevant:
                events.append(ievent)
        return events

class ICalendarEvent(object):
    def __init__(self, event, tzinfo=None):
        self.summary = event.get('SUMMARY')
        self.start = event.get('DTSTART').dt
        self.end = event.get('DTEND').dt
        if type(self.start) is datetime.datetime:
            self.start = self.start.astimezone(tzinfo)
        if type(self.end) is datetime.datetime:
            self.end = self.end.astimezone(tzinfo)

    def getSummary(self):
        return self.summary
    def getStart(self):
        return self.start
    def getEnd(self):
        return self.end
    def isAllDay(self):
        return type(self.start) is datetime.date and type(self.end) is datetime.date
    def occursOn(self, date):
        dateIso = date.isoformat()
        nextDateIso = (date + datetime.timedelta(days=1)).isoformat()
        startIso = self.start.isoformat()
        endIso = self.end.isoformat()
        return ((startIso <= dateIso and endIso > dateIso) 
                or (startIso >= dateIso and startIso < nextDateIso)
                or (endIso >= dateIso and endIso < nextDateIso)
                and not endIso == dateIso)
