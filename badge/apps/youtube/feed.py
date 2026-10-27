import json

MAX_FEED_BYTES = 256 * 1024
VIDEO_LIMIT = 6


def calendar_day(year, month, day):
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    months = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if year < 1 or not 1 <= month <= 12 or not 1 <= day <= months[month - 1]:
        raise ValueError("Invalid publication date")
    previous = year - 1
    return (365 * previous + previous // 4 - previous // 100 + previous // 400
            + sum(months[:month - 1]) + day)


def relative_date(published, today):
    year, month, day = int(published[:4]), int(published[5:7]), int(published[8:10])
    age = calendar_day(*today[:3]) - calendar_day(year, month, day)
    if today[0] < 2024 or age < 0:
        return "Check badge clock"
    if age == 0:
        return "Today"
    if age == 1:
        return "Yesterday"
    if age < 7:
        return "%d days ago" % age
    if age < 14:
        return "A week ago"
    if age < 31:
        return "%d weeks ago" % (age // 7)
    if age < 60:
        return "More than a month ago"
    if age < 365:
        return "%d months ago" % (age // 30)
    if age < 730:
        return "A year ago"
    return "%d years ago" % (age // 365)


def read_clock(path):
    with open(path, "r") as handle:
        payload = json.loads(handle.read(4096))
    year, month, day = (int(payload[key]) for key in ("year", "month", "day"))
    hour, minute, second = (int(payload[key]) for key in ("hour", "minute", "seconds"))
    ordinal = calendar_day(year, month, day)
    if year < 2024 or not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        raise ValueError("Invalid clock response")
    if payload.get("timeZone") != "UTC":
        raise ValueError("Clock response must be UTC")
    return year, month, day, (ordinal - 1) % 7, hour, minute, second, 0


def unescape(text):
    if text.startswith("<![CDATA[") and text.endswith("]]>"):
        return text[9:-3]
    parts = text.split("&")
    result = parts[0]
    entities = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'", "nbsp": " "}
    for part in parts[1:]:
        end = part.find(";")
        entity = part[:end] if end >= 0 else ""
        replacement = entities.get(entity)
        if entity.startswith("#"):
            try:
                replacement = chr(int(entity[2:], 16) if entity[1:2].lower() == "x"
                                  else int(entity[1:]))
            except (ValueError, OverflowError):
                replacement = None
        if replacement is None:
            result += "&" + part
        else:
            result += replacement + part[end + 1:]
    return result


def field(entry, name):
    start_tag = "<" + name + ">"
    end_tag = "</" + name + ">"
    start = entry.find(start_tag)
    if start < 0:
        return ""
    end = entry.find(end_tag, start + len(start_tag))
    if end < 0:
        raise ValueError("Incomplete " + name)
    return unescape(entry[start + len(start_tag):end]).strip()


def view_count(entry):
    start = entry.find("<media:statistics ")
    if start < 0:
        return None
    end = entry.find(">", start)
    if end < 0:
        raise ValueError("Incomplete view statistics")
    attributes = entry[start:end]
    for quote in ('"', "'"):
        marker = "views=" + quote
        position = attributes.find(marker)
        if position >= 0:
            value = attributes[position + len(marker):].split(quote, 1)[0]
            if not value or not all(char in "0123456789" for char in value):
                raise ValueError("Invalid view count")
            return int(value)
    return None


def video_url(video_id):
    if not valid_id(video_id, 11):
        raise ValueError("Invalid video ID")
    return "https://youtu.be/" + video_id


def valid_id(value, length):
    return len(value) == length and all(
        char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
        for char in value
    )


def parse_feed(text, channel_id):
    if len(text) > MAX_FEED_BYTES:
        raise ValueError("YouTube feed is too large")
    if "<feed " not in text or "</feed>" not in text:
        raise ValueError("Incomplete YouTube feed")
    videos = []
    seen = set()
    offset = 0
    while True:
        start = text.find("<entry>", offset)
        if start < 0:
            break
        end = text.find("</entry>", start)
        next_entry = text.find("<entry>", start + len("<entry>"))
        if end < 0 or (next_entry >= 0 and next_entry < end):
            raise ValueError("Incomplete video entry")
        entry = text[start:end]
        offset = end + len("</entry>")
        video_id = field(entry, "yt:videoId")
        title = field(entry, "title")
        published = field(entry, "published")
        if field(entry, "yt:channelId") != channel_id:
            raise ValueError("Feed belongs to a different channel")
        if not valid_id(video_id, 11) or not title or len(published) < 10:
            raise ValueError("Invalid video entry")
        calendar_day(int(published[:4]), int(published[5:7]), int(published[8:10]))
        if video_id not in seen:
            seen.add(video_id)
            videos.append({
                "id": video_id,
                "title": " ".join(title.split()),
                "published": published,
                "views": view_count(entry),
            })
    videos.sort(key=lambda video: video["published"], reverse=True)
    return videos[:VIDEO_LIMIT]


def read_feed(path, channel_id):
    with open(path, "r") as handle:
        text = handle.read(MAX_FEED_BYTES + 1)
    return parse_feed(text, channel_id)


def thumbnail_url(video_id):
    if not valid_id(video_id, 11):
        raise ValueError("Invalid video ID")
    return ("https://wsrv.nl/?url=https%3A%2F%2Fi.ytimg.com%2Fvi%2F" + video_id
            + "%2Fmqdefault.jpg&w=192&h=108&fit=cover&output=png")
