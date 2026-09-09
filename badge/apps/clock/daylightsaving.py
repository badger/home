# Code modified from Beormund on GitHub: https://gist.github.com/Beormund/f0f39c72e066da497f6308d1964c9627

import utime


# hemisphere [0 = Northern, 1 = Southern]
# week [0 = last week of month, 1..4 = first..fourth]
# month [1 = January; 12 = December]
# weekday [0 = Monday; 6 = Sunday] (day of week)
# hour (hour at which dst/std changes)
# timezone [-780..780] (offset from UTC in MINUTES - 780min / 60min=13hrs)
class Policy:
    def __init__(self, hemisphere, week, month, weekday, hour, timezone):
        if hemisphere not in [0, 1]:
            raise ValueError("hemisphere must be 0..1")
        if week not in range(5):
            raise ValueError("week must be 0 or 1..4")
        if month not in range(1, 13):
            raise ValueError("month must be 1..12")
        if weekday not in range(7):
            raise ValueError("weekday must be 0..6")
        if hour not in range(24):
            raise ValueError("hour must be 0..23")
        if timezone not in range(-780, 781):
            raise ValueError("timezone must be -780..780")
        self.hemisphere = hemisphere
        self.week = week
        self.month = month
        self.weekday = weekday
        self.hour = hour
        self.timezone = timezone

    def __str__(self):
        self.days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        self.abbr = ["last", "first", "second", "third", "fourth"]
        self.months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return ("Daylight Saving Policy: daylight saving {} on the {} {} of {} at {:02}:00 hrs (UTC{})").format(
            self.prefix,
            self.abbr[self.week],
            self.days[self.weekday],
            self.months[self.month - 1],
            self.hour,
            "" if not self.timezone else "{:+1}".format(self.timezone / 60)
        )


class StandardTimePolicy(Policy):
    def __init__(self, hemisphere, week, month, weekday, hour, timezone):
        self.prefix = "ends"
        super(StandardTimePolicy, self).__init__(hemisphere, week, month, weekday, hour, timezone)


class DaylightSavingPolicy(Policy):
    def __init__(self, hemisphere, week, month, weekday, hour, timezone):
        self.prefix = "starts"
        super(DaylightSavingPolicy, self).__init__(hemisphere, week, month, weekday, hour, timezone)


class DaylightSaving:
    def __init__(self, dstp, stdp):
        self.dstp = dstp
        self.stdp = stdp
        print(self.dstp)
        print(self.stdp)

    def isleapyear(self, year):
        return (year % 4 == 0 and year % 100 != 0) or year % 400 == 0

    def increment_dom(self, d):
        return d + 1 if d < 6 else 0

    def decrement_dom(self, d):
        return d - 1 if d > 0 else 6

    def dayofmonth(self, week, month, weekday, day, year):
        # Get the first or last day of the month
        t = utime.mktime((year, month, day, 0, 0, 0, 0, 0))
        # Get the weekday of the first or last day of the month
        d = utime.localtime(t)[6]
        increment = self.increment_dom
        decrement = self.decrement_dom
        while d != weekday:
            # Increment if start of month else decrement
            day = day + 1 if week else day - 1
            d = increment(d) if week else decrement(d)
        # Increment day of month by number of weeks
        return day + (week - 1) * 7 if week else day

    def nthweekday(self, week, month, weekday, hour, year):
        monthlength = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        if self.isleapyear(year):
            monthlength[1] = 29
        day = 1 if week else monthlength[month - 1]
        day = self.dayofmonth(week, month, weekday, day, year)
        return utime.mktime((year, month, day, hour, 0, 0, 0, 0))

    def gettfromp(self, p, year):
        return self.nthweekday(p.week, p.month, p.weekday, p.hour, year)

    def localtime(self, utc):
        year = utime.gmtime(utc)[0]
        dst = self.gettfromp(self.dstp, year)
        std = self.gettfromp(self.stdp, year)
        saving = False
        if self.stdp.hemisphere:
            # Sourthern hemisphere
            saving = utc > dst or utc < std
        else:
            # Northern hemisphere
            saving = utc > dst and utc < std
        offset = self.dstp.timezone if saving else self.stdp.timezone
        return utc + (offset * 60)

    def ftime(self, t):
        year, month, day, hour, minute, second, ms, dayinyear = utime.localtime(t)
        return "{:4}-{:02}-{:02}T{:02}:{:02}:{:02}".format(year, month, day, hour, minute, second)
