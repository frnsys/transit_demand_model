import enum
import pandas as pd
from datetime import timedelta


class ServiceChange(enum.Enum):
    """https://developers.google.com/transit/gtfs/reference/#calendar_datestxt"""
    ADDED   = 1
    REMOVED = 2


class Weekday(enum.Enum):
    MONDAY    = 0
    TUESDAY   = 1
    WEDNESDAY = 2
    THURSDAY  = 3
    FRIDAY    = 4
    SATURDAY  = 5
    SUNDAY    = 6


class Calendar:
    def __init__(self, gtfs):
        """parse calendar data for service days/changes/exceptions"""
        # associate services with their operating weekdays
        # NOTE this data provies start and end dates for services
        # but for our simulation we are treating this timetable as ongoing
        calendar = gtfs['calendar']
        service_days = {day: [] for day in Weekday}
        for i, row in calendar.iterrows():
            service_id = row.service_id
            for day, services in service_days.items():
                if row[day.name.lower()] == 1:
                    services.append(service_id)
        self.service_days = service_days

        # parse 'date' column as date objects
        # then group by date, so we can quickly query
        # service changes for a given date
        service_changes = gtfs['calendar_dates']
        service_changes['date'] = pd.to_datetime(service_changes.date, format='%Y%m%d').dt.date
        self.service_changes = service_changes.groupby('date')

        # map service_id->[trip_ids]
        self.services = {name: group['trip_id'].values
                         for name, group in gtfs['trips'].groupby('service_id')}

    def services_for_dt(self, dt):
         """returns operating service ids
         for a given datetime"""
         # gives weekday as an int,
         # where `monday = 0`
         weekday = Weekday(dt.weekday())

         # get list of service ids as a copy
         # so we can add/remove according to service changes
         services = self.service_days[weekday][:]

         # check if there are any service changes for the date
         for service_id, change in self.service_changes_for_dt(dt).items():
             if change is ServiceChange.ADDED:
                 services.append(service_id)
             else:
                 try:
                     services.remove(service_id)
                 except ValueError:
                     pass
         return services

    def service_changes_for_dt(self, dt):
         """return a dict of `{service_id: ServiceChange}`
         describing service changes (additions or removals
         for a given datetime"""
         try:
             changes = self.service_changes.get_group(dt.date())
             return {c.service_id: ServiceChange(c.exception_type) for i, c in changes.iterrows()}
         except KeyError:
             return {}

    def trips_for_services(self, service_ids):
         """get trip ids that encompass a given list of service ids"""
         trips = set()
         for service_id in service_ids:
             trip_ids = self.services.get(service_id, [])
             trips = trips | set(trip_ids)
         return trips
