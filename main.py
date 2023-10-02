#!/usr/bin/env python3
if __name__ != '__main__':
    print('Must run as script')
    sys.exit(1)

from waveshare_epd import epd7in5_V2
from PIL import Image,ImageDraw,ImageFont
import time, sched, os, sys, calendar, calendar_loader, json, datetime

fontsdirname = 'fonts'
calendar_list_filename = 'calendars.json'
calendar_cache_dirname = 'calendar_cache'

epd = epd7in5_V2.EPD()

home = os.path.abspath(os.path.dirname(__file__))
fontbasedir = os.path.join(home, fontsdirname)
calendar_list_file = os.path.join(home, calendar_list_filename)
calendar_cache_dir = os.path.join(home, calendar_cache_dirname)
calendars = []

if os.path.isfile(calendar_list_file):
    try:
        with open(calendar_list_file, 'r') as infil:
            calendars = json.load(infil)
    except Exception as e:
        print('Unable to load calendar list file; continuing with no calendars loaded')

event_sources = [calendar_loader.ICalendarCacheWrapper(calendar, cache_dir=calendar_cache_dir) for calendar in calendars]

majorFontName = os.path.join(fontbasedir, 'SFAlienEncountersSolid.ttf')
minorFontName = os.path.join(fontbasedir, 'Audiowide-Regular.ttf')
minimumFontName = os.path.join(fontbasedir, 'RictyDiminished-Bold.ttf')

def boundsToSize(bounds):
    return [(bounds[2]-bounds[0]), (bounds[3]-bounds[1])]
def bbFitWithin(fittingBB, fitIntoBB):
    fittingSize = boundsToSize(fittingBB)
    fitIntoSize = boundsToSize(fitIntoBB)
    return fittingSize[0] <= fitIntoSize[0] and fittingSize[1] <= fitIntoSize[1]
## Font here is the path to the font, not a font object
def getMaximumFontSize(font, maxSize, testStr):
  testSize = 1
  lastSize = False
  fitBB = [0, 0, maxSize[0], maxSize[1]]
  while True:
      fontDraw = ImageFont.truetype(font, testSize)
      fits = bbFitWithin(fontDraw.getbbox(testStr, anchor='lb'), fitBB)
      if fits:
          lastSize = testSize
          lastFit = True
          testSize += 1
      elif (not fits) and lastFit:
          return lastSize
      elif (not fits) and testSize == 1:
          # Escape from infinite loop; if even 1 won't fit, we can't print into this space
          raise Exception('Can\'t fit font {font:s} into bounding box {bb:g}'.format(font=font, bb=maxSize))


## Constraints on drawing
edgeBuffer = 2 # pixel buffer from the edges of the e-paper
interItemBuffer = 3 # pixel buffer between components
calendarXSize = 0.7
headerYSize = 0.1
dowYSize = 0.03
dateHeaderHeightPct = 0.15 # 15% of the height of the box
dateHeaderWidthPct = 0.3  # two-digit dates should be 30% of the width of the box
dateContentsBufferPct = 0.1 # 10% of the size of the box
dateEventBoxMinimumSize = 3 # 3px of box
dateEventBoxMaximumSize = 20 # 10px of box
dateEventBoxMinimumSeparation = 2 # 2px of separation
dateEventTestString = 'a few words'
dateEventMinimumHeight = 12
dateEventMaximumHeight = 24

# colors
foreground = 0
background = 1

# Overall setup
headerBounds = [edgeBuffer, edgeBuffer, int(epd.width*calendarXSize)-edgeBuffer-interItemBuffer, int(epd.height*headerYSize)]
dayHeaderBounds = [headerBounds[2]+interItemBuffer, edgeBuffer, epd.width-edgeBuffer, headerBounds[3]]
calendarDoWBounds = [headerBounds[0], headerBounds[3]+interItemBuffer, headerBounds[2], headerBounds[3]+interItemBuffer+int(epd.height*dowYSize)]
calendarGridBounds = [edgeBuffer, calendarDoWBounds[3]+interItemBuffer, headerBounds[2], epd.height-edgeBuffer]
dayBounds = [calendarGridBounds[2]+interItemBuffer, dayHeaderBounds[3]+interItemBuffer, epd.width-edgeBuffer, epd.height-edgeBuffer]
daySize = [dayBounds[2] - dayBounds[0], dayBounds[3] - dayBounds[0]]

## Calendar specific settings
# 7 days in a week, maximum 5 weeks in a month
daysInWeek = 7
weeksInMonth = 5
calendarGridSize = [calendarGridBounds[2] - calendarGridBounds[0], calendarGridBounds[3] - calendarGridBounds[1]]
calendarGridDaySize = [int(calendarGridSize[0]/float(daysInWeek)), int(calendarGridSize[1]/float(weeksInMonth))]
calendarGridBounds = [calendarGridBounds[0], calendarGridBounds[1], calendarGridBounds[0]+calendarGridDaySize[0]*daysInWeek, calendarGridBounds[1]+calendarGridDaySize[1]*weeksInMonth]
calendarGridXLines = [x*calendarGridDaySize[0] for x in range(7)]
calendarGridYLines = [y*calendarGridDaySize[1] for y in range(5)]

# Height of the date header on each calendar box
dateHeaderHeight = int(dateHeaderHeightPct*calendarGridDaySize[1])
# Offset from minimum box x of where the date number ends
dateHeaderWidth = int(dateHeaderWidthPct*calendarGridDaySize[0])
# How much buffer is on each side of the event contents of a date
dateContentsBufferSize = [int(dateContentsBufferPct*calendarGridDaySize[0]), int(dateContentsBufferPct*calendarGridDaySize[1])]
# Offset from the box x,y (upper left) of the event contents
dateContentsBounds = [dateContentsBufferSize[0], dateContentsBufferSize[1]+dateHeaderHeight, calendarGridDaySize[0]-dateContentsBufferSize[0], calendarGridDaySize[1]-dateContentsBufferSize[1]]
dateEventsSize = [dateContentsBounds[2]-dateContentsBounds[0], dateContentsBounds[3]-dateContentsBounds[1]]
dateEventsBottomMiddle = [int(dateEventsSize[0]/2)+dateContentsBounds[0], dateContentsBounds[3]-interItemBuffer]
dateHeaderFont = ImageFont.truetype(minorFontName, getMaximumFontSize(minorFontName, [dateHeaderWidth-4, dateHeaderHeight-4], '00'))
dateContentsFont = ImageFont.truetype(minorFontName, getMaximumFontSize(minorFontName, [dateEventsSize[0]-4, dateEventsSize[1]-4], '000'))

def drawCalendarGrid(draw):
    # Draw day-of-week headers
    daysOfWeek = [dbr for dbr in calendar.day_abbr]
    longest_day_abbreviation = daysOfWeek[daysOfWeek.index(sorted(daysOfWeek, key=lambda i: len(i), reverse=True)[0])]
    font = ImageFont.truetype(minorFontName, getMaximumFontSize(minorFontName,
                                              [calendarGridDaySize[0]-2, calendarDoWBounds[3]-calendarDoWBounds[1]-2],
                                              longest_day_abbreviation))
    for x in range(daysInWeek):
        gridX = (x*calendarGridDaySize[0])+calendarDoWBounds[0]
        dayOfWeek = calendar.day_abbr[(x+daysInWeek-1)%daysInWeek]
        draw.text((gridX, calendarDoWBounds[1]+2), dayOfWeek, font=font, anchor='lt', fill=foreground)
    # Draw column separators
    for x in range(daysInWeek+1):
        gridX = (x * calendarGridDaySize[0]) + calendarGridBounds[0]
        draw.line([(gridX, calendarGridBounds[1]), (gridX, calendarGridBounds[3])], fill=foreground)
    # Draw row separators
    for y in range(weeksInMonth+1):
        gridY = (y * calendarGridDaySize[1]) + calendarGridBounds[1]
        draw.line([(calendarGridBounds[0], gridY), (calendarGridBounds[2], gridY)], fill=foreground)
        # Header lines
        if y < weeksInMonth:
          draw.line([(calendarGridBounds[0], gridY + dateHeaderHeight), (calendarGridBounds[2], gridY + dateHeaderHeight)], fill=foreground)

def drawDateContents(draw, x, y, dateNumber, highlightHeader=None, events=None, currentMonth=None):
  if highlightHeader is None:
      highlightHeader = False
  if currentMonth is None:
      currentMonth = True
  upLeft = [x*calendarGridDaySize[0]+calendarGridBounds[0], y*calendarGridDaySize[1]+calendarGridBounds[1]]
  draw.text([upLeft[0]-2+dateHeaderWidth, upLeft[1]+2], str(dateNumber), font=dateHeaderFont, anchor='rt', fill=foreground)
  draw.line([(upLeft[0]+dateHeaderWidth, upLeft[1]), (upLeft[0]+dateHeaderWidth, upLeft[1]+dateHeaderHeight)], fill=foreground)
  if highlightHeader:
      draw.rectangle((upLeft[0]+dateHeaderWidth, upLeft[1], upLeft[0]+(calendarGridDaySize[0]), upLeft[1]+dateHeaderHeight), fill=foreground)
  if not currentMonth:
      draw.line([(upLeft[0], upLeft[1]+dateHeaderHeight), (upLeft[0]+calendarGridDaySize[0], upLeft[1]+calendarGridDaySize[1])], fill=foreground)
  if events is not None and len(events) > 0 and currentMonth:
      eventCount = len(events)
      allDayCount = len([event for event in events if event.isAllDay()])
      # We want a number of boxes equal to the number of events, unless we can't fit at least 3px of box and 1px of separation;
      #  then we just output a filled rectangle with a number.
      if dateEventsSize[1] < eventCount*dateEventMinimumHeight + (eventCount-1)*dateEventBoxMinimumSeparation:
          draw.rectangle([(upLeft[0]+dateContentsBounds[0], upLeft[1]+dateContentsBounds[1]), (upLeft[0]+dateContentsBounds[2], upLeft[1]+dateContentsBounds[3])], fill=background, outline=foreground, width=2)
          draw.text([dateEventsBottomMiddle[0]+upLeft[0], dateEventsBottomMiddle[1]+upLeft[1]], str(eventCount), font=dateContentsFont, anchor='mb', fill=foreground)
      else:
          # If we can fit it, we'll use 2xminimum separation
          separation = dateEventBoxMinimumSeparation
          if dateEventsSize[0] >= eventCount*dateEventMinimumHeight + (eventCount-1)*2*separation:
              separation *= 2
          boxSize = min(max(int( (dateEventsSize[1]-(separation*eventCount-1))/eventCount), dateEventMinimumHeight), dateEventMaximumHeight)
          dateEventFont = ImageFont.truetype(minimumFontName, getMaximumFontSize(minimumFontName, [dateEventsSize[0], boxSize-4], dateEventTestString))
          for yc in range(eventCount):
              eUpLeft = (upLeft[0]+dateContentsBounds[0], upLeft[1]+dateContentsBounds[1]+yc*(boxSize+separation))
              eBotRight = (upLeft[0]+dateContentsBounds[2], upLeft[1]+dateContentsBounds[1]+yc*(boxSize+separation)+boxSize)
              draw.rectangle([eUpLeft, eBotRight], outline=foreground, fill=background)
              draw.text([eUpLeft[0]+2, eUpLeft[1]+2], getFittedText(draw, dateEventFont, events[yc].getSummary(), dateEventsSize[0]-4), font=dateEventFont, anchor='lt', fill=foreground)

def getFittedText(draw, imageFont, text, widthToFit):
    textCopy = text
    testLength = draw.textlength(textCopy, imageFont)
    while testLength > widthToFit:
        if len(textCopy) == 0:
            raise Exception('Can\'t fit text {:s}'.format(text))
        if testLength > widthToFit*2:
            textCopy = textCopy[:int(len(textCopy)/2)]
        else:
            textCopy = textCopy[:-1]
        testLength = draw.textlength(textCopy, imageFont)
    return textCopy

def drawCalendarHeader(draw, date):
  upLeft = headerBounds[0:2]
  dateStr = date.strftime('%B %d %Y')
  headerSize = [(headerBounds[2] - headerBounds[0])-4, (headerBounds[3] - headerBounds[1])-4]
  font = ImageFont.truetype(majorFontName, getMaximumFontSize(majorFontName, headerSize, dateStr))
  draw.text((upLeft[0], upLeft[1]), dateStr, font=font, anchor='lt', fill=foreground)

## Day events specific settings
# fill things in here
def drawDayHeader(draw):
  title = 'Today'
  upLeft = dayHeaderBounds[0:2]
  headerSize = [(dayHeaderBounds[2] - dayHeaderBounds[0])-4, (dayHeaderBounds[3] - dayHeaderBounds[1])-4]
  font = ImageFont.truetype(majorFontName, getMaximumFontSize(majorFontName, headerSize, title))
  draw.text((upLeft[0], upLeft[1]), title, font=font, anchor='lt', fill=foreground)

def drawDayGrid(draw):
  draw.rectangle([(dayBounds[0], dayBounds[1]), (dayBounds[2], dayBounds[3])], width=2, fill=background, outline=foreground)


def drawCalendar():
    print('Formatting calendar')
    preCal = datetime.datetime.now()
    timeImage = Image.new('1', (epd.width, epd.height), 1)
    draw = ImageDraw.Draw(timeImage)

    now = datetime.datetime.now(calendar_loader.currenttz())
    curDate = now.date()
    cal = calendar.Calendar(6)
    datesBeingDrawn = [date for date in cal.itermonthdates(curDate.year, curDate.month)]
    earliestDateDrawn = datesBeingDrawn[0]
    events = []
    for wrappedCalendar in event_sources:
        events += wrappedCalendar.get_events_after(earliestDateDrawn)
    events.sort(key=lambda event: event.getStart().isoformat())

    drawCalendarHeader(draw, curDate)
    drawDayHeader(draw)

    drawCalendarGrid(draw)
    for idx, dateObj in enumerate(datesBeingDrawn):
        thisDayEvents = [event for event in events if event.occursOn(dateObj)]
        gridLocation = [(dateObj.weekday()+1)%7, int(idx/7)]
        drawDateContents(draw, gridLocation[0], gridLocation[1],
                  dateObj.day, highlightHeader=curDate == dateObj,
                  currentMonth = curDate.month == dateObj.month,
                  events=thisDayEvents)
    
    todayEvents = [event for event in events if event.occursOn(curDate)]
    drawDayGrid(draw)
    print('Ouputting to display')
    preDraw = datetime.datetime.now()
    try:

        epd.init()
        epd.Clear()
        epd.display(epd.getbuffer(timeImage))
    finally:
        epd.sleep()
    after = datetime.datetime.now()
    formatTime = preDraw - preCal
    outputTime = after - preDraw
    print('Complete; Formatting {:.2f}s, drawing {:.2f}s'.format(formatTime.total_seconds(), outputTime.total_seconds()))

drawCalendar()
