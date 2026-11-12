"""Dialect-aware time bucketing in local time (IST = UTC+5:30). Storage is UTC."""
from sqlalchemy import func, text
from ..core.db import engine

IS_SQLITE = engine.dialect.name == "sqlite"


def local(col):
    return func.datetime(col, "+330 minutes") if IS_SQLITE else func.timezone("Asia/Kolkata", col)


def bucket(col, gran: str):
    l = local(col)
    if IS_SQLITE:
        fmt = {"hour": "%Y-%m-%dT%H:00", "day": "%Y-%m-%d", "month": "%Y-%m", "week": None}[gran]
        if gran == "week":
            return func.strftime("%Y-W%W", l)
        return func.strftime(fmt, l)
    if gran == "week":
        return func.to_char(l, 'IYYY-"W"IW')
    fmt = {"hour": 'YYYY-MM-DD"T"HH24:00', "day": "YYYY-MM-DD", "month": "YYYY-MM"}[gran]
    return func.to_char(l, fmt)


def local_hour(col):
    l = local(col)
    return func.cast(func.strftime("%H", l), type_=__import__("sqlalchemy").Integer) if IS_SQLITE else func.extract("hour", l)
