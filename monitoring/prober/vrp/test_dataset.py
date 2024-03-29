"""
Test Eurocontrol's dataset'
"""

import datetime
import itertools
from typing import Literal
import pandas as pd

from monitoring.prober.infrastructure import depends_on, IDFactory
from monitoring.monitorlib.infrastructure import DSSTestSession
from monitoring.monitorlib.typing import ImplicitDict, StringBasedDateTime
from monitoring.monitorlib.formatting import make_datetime

SCOPE_VRP = 'utm.vertiport_management'

VRP_DEPARTURES = []

VERTIPORTS_IDS = []

MAX_HOVER_MIN = 15
MAX_DELAY_MIN = 60

DELAY_MIN = 1

RESERVATION_TIME_MIN = 2.5

def read_vrp1_departures():
    filename = "/monitoring/prober/vrp/RandomDemand.xlsx"
    vrp1_departures_df = pd.read_excel(filename, sheet_name='Departure from Vertiport 1', \
        dtype={'Flight ID': str, 'Start Vertiport 1': str, \
        'Destination Vertiport 2': str, 'Destination Vertiport 3': str})

    vrp1_departures_list = []

    for idx, row in vrp1_departures_df.iterrows():
        dest_vrp = 2 if not pd.isna(row['Destination Vertiport 2']) else 3

        departure_datetime_str = row['Start Vertiport 1']
        departure_datetime_obj = datetime.datetime.strptime(departure_datetime_str, '%Y-%m-%d %H:%M:%S')

        arrival_datetime_str = row['Destination Vertiport 2'] \
            if dest_vrp==2 \
            else row['Destination Vertiport 3']

        arrival_datetime_obj = datetime.datetime.strptime(arrival_datetime_str, '%Y-%m-%d %H:%M:%S')

        departure_datetime_obj = departure_datetime_obj + datetime.timedelta(days=365)
        arrival_datetime_obj = arrival_datetime_obj + datetime.timedelta(days=365)

        one_flight_dict = {
            "ID Departure": IDFactory('OP{}_{}_{}'.format(idx, 1, dest_vrp)).make_id(idx),
            "ID Arrival": IDFactory('OP{}_{}_{}2'.format(idx, 1, dest_vrp)).make_id(idx),
            "Flight ID": row['Flight ID'],
            "Origin Vertiport": 1,
            "Destination Vertiport": dest_vrp,
            "Departure Time": departure_datetime_obj,
            "Arrival Time":  arrival_datetime_obj
        }
        vrp1_departures_list.append(one_flight_dict)
    return vrp1_departures_list


def read_vrp2_departures():
    filename = "/monitoring/prober/vrp/RandomDemand.xlsx"

    vrp2_departures_df = pd.read_excel(filename, sheet_name='Departure from Vertiport 2', \
        dtype={'Flight ID': str, 'Start Vertiport 2': str, \
        'Destination Vertiport 1': str, 'Destination Vertiport 3': str})

    vrp2_departures_list = []
    for idx, row in vrp2_departures_df.iterrows():

        dest_vrp = 1 if not pd.isna(row.loc['Destination Vertiport 1']) else 3

        departure_datetime_str = row['Start Vertiport 2']
        departure_datetime_obj = datetime.datetime.strptime(departure_datetime_str, '%Y-%m-%d %H:%M:%S')

        arrival_datetime_str = row['Destination Vertiport 1'] \
            if dest_vrp==1 \
            else row['Destination Vertiport 3']

        arrival_datetime_obj = datetime.datetime.strptime(arrival_datetime_str, '%Y-%m-%d %H:%M:%S')

        departure_datetime_obj = departure_datetime_obj + datetime.timedelta(days=365)
        arrival_datetime_obj = arrival_datetime_obj + datetime.timedelta(days=365)

        one_flight_dict = {
            "ID Departure": IDFactory('OP{}_{}_{}'.format(idx, 2, dest_vrp)).make_id(idx),
            "ID Arrival": IDFactory('OP{}_{}_{}2'.format(idx, 2, dest_vrp)).make_id(idx),
            "Flight ID": row['Flight ID'],
            "Origin Vertiport": 2,
            "Destination Vertiport": dest_vrp,
            "Departure Time": departure_datetime_obj,
            "Arrival Time":  arrival_datetime_obj
        }
        vrp2_departures_list.append(one_flight_dict)
    return vrp2_departures_list


def read_vrp3_departures():
    filename = "/monitoring/prober/vrp/RandomDemand.xlsx"

    vrp3_departures_df = pd.read_excel(filename, sheet_name='Departure from Vertiport 3', \
        dtype={'Flight ID': str, 'Start Vertiport 3': str, \
        'Destination Vertiport 1': str, 'Destination Vertiport 2': str})

    vrp3_departures_list = []
    for idx, row in vrp3_departures_df.iterrows():

        dest_vrp = 1 if not pd.isna(row['Destination Vertiport 1']) else 2

        departure_datetime_str = row['Start Vertiport 3']
        departure_datetime_obj = datetime.datetime.strptime(departure_datetime_str, '%Y-%m-%d %H:%M:%S')

        arrival_datetime_str = row['Destination Vertiport 1'] \
            if dest_vrp==1 \
            else row['Destination Vertiport 2']

        arrival_datetime_obj = datetime.datetime.strptime(arrival_datetime_str, '%Y-%m-%d %H:%M:%S')

        departure_datetime_obj = departure_datetime_obj + datetime.timedelta(days=365)
        arrival_datetime_obj = arrival_datetime_obj + datetime.timedelta(days=365)


        one_flight_dict = {
            "ID Departure": IDFactory('OP{}_{}_{}'.format(idx, 3, dest_vrp)).make_id(idx),
            "ID Arrival": IDFactory('OP{}_{}_{}2'.format(idx, 3, dest_vrp)).make_id(idx),
            "Flight ID": row['Flight ID'],
            "Origin Vertiport": 3,
            "Destination Vertiport": dest_vrp,
            "Departure Time": departure_datetime_obj,
            "Arrival Time":  arrival_datetime_obj
        }
        vrp3_departures_list.append(one_flight_dict)
    return vrp3_departures_list


class Time(ImplicitDict):
    ''' A class to hold Time details '''
    value: StringBasedDateTime
    format:Literal['RFC3339']

def make_time(t: datetime) -> Time:
    return Time(value=t.isoformat() + 'Z', format='RFC3339')

BASE_URL = 'https://example.com/uss'


def _make_op_request(vertiport_id, vertiport_zone, time_start, time_end):
  return {
    'vertiport_reservation':
        {'time_start': make_time(time_start),
         'time_end': make_time(time_end),
         'vertiportid': vertiport_id,
         'reserved_zone': vertiport_zone,
        },
    'old_version': 0,
    'state': 'Accepted',
    'uss_base_url': BASE_URL,
    'new_subscription': {
        'uss_base_url': BASE_URL,
        'notify_for_constraints': False
    }
  }


def delete_operation_if_exists(id: str, vrp_session: DSSTestSession):
    url = '/operational_intent_references/{}'
    resp = vrp_session.get(url.format(id), scope=SCOPE_VRP)
    if resp.status_code == 200:
        ovn = resp.json()['operational_intent_reference']['ovn']
        resp = vrp_session.delete('/operational_intent_references/{}/{}'.format(id, ovn), scope=SCOPE_VRP)
        assert resp.status_code == 200, resp.content
    elif resp.status_code == 404:
        # As expected.
        pass
    else:
        assert False, resp.content


def setup_module(vrp_session):
    global VRP_DEPARTURES, VERTIPORTS_IDS

    VERTIPORTS_IDS = [IDFactory('Vertiport 1').make_id(1), IDFactory('Vertiport 2').make_id(1), IDFactory('Vertiport 3').make_id(1)]
    vrp1_departures = read_vrp1_departures()
    vrp2_departures = read_vrp2_departures()
    vrp3_departures = read_vrp3_departures()


    VRP_DEPARTURES = sorted(
        list(itertools.chain(vrp1_departures, vrp2_departures, vrp3_departures)),
        key=lambda x: x['Departure Time']
    )


# Delete Operations if exist
# Preconditions: None
# Mutations: Operations deleted if exist
def test_ensure_clean_workspace(ids, vrp_session):
    for vrp_id in VERTIPORTS_IDS:
        resp = vrp_session.get('/{}'.format(vrp_id), scope=SCOPE_VRP)

        if resp.status_code == 200:
            resp = vrp_session.delete('/{}'.format(vrp_id), scope=SCOPE_VRP)

            assert resp.status_code == 200

    for operation in VRP_DEPARTURES:
        delete_operation_if_exists(operation['ID Departure'], vrp_session)
        delete_operation_if_exists(operation['ID Arrival'], vrp_session)


# Create vertiports
# Preconditions: None
# Mutations: vertiports created
def test_create_vertiports(ids, vrp_session):
    for vrp_id in VERTIPORTS_IDS:
        resp = vrp_session.put('/{}'.format(vrp_id), json={'number_of_parking_places': 5}, scope=SCOPE_VRP)
        assert resp.status_code == 200, resp.content


def find_first_available_time_period(time_periods):
    for time_period in time_periods:
        t_from = make_datetime(time_period['from']['value'])
        t_to = make_datetime(time_period['to']['value'])

        t_from = t_from.replace(tzinfo=None)
        t_to = t_to.replace(tzinfo=None)

        if t_to - t_from > datetime.timedelta(minutes=RESERVATION_TIME_MIN):
            return (t_from, t_to)
        else:
            print((time_period, t_from, t_to, t_to - t_from))

    return None


def schedule_flights(vrp_session, orig_vrp_id, intended_start_time, planned_flight_time, dest_vrp_id):
    resp = vrp_session.post('/fato_available_times/{}'.format(orig_vrp_id), json={
        'time_start': make_time(intended_start_time),
        'time_end': make_time(intended_start_time + datetime.timedelta(minutes=MAX_DELAY_MIN))
    }, scope=SCOPE_VRP)

    data = resp.json()
    time_period = find_first_available_time_period(data['time_period'])

    if time_period is None:
        raise Exception('No available time period!')

    real_time_start = time_period[0]

    intended_end_time = real_time_start + planned_flight_time

    resp = vrp_session.post('/fato_available_times/{}'.format(dest_vrp_id), json={
        'time_start': make_time(intended_end_time),
        'time_end': make_time(intended_end_time + datetime.timedelta(minutes=MAX_HOVER_MIN))
    }, scope=SCOPE_VRP)

    data = resp.json()
    time_period = find_first_available_time_period(data['time_period'])

    if time_period is None:
        raise Exception('No available time period!')

    real_time_arrival = time_period[0]

    return real_time_start, real_time_arrival


# Create Operations (also create implicit Subscriptions)
# Preconditions: None
# Mutations: Operations created by vrp_session user
@depends_on(test_ensure_clean_workspace)
def test_create_ops(ids, vrp_session):
    for ind, departure in enumerate(VRP_DEPARTURES):
        orig_vrp_id = VERTIPORTS_IDS[departure['Origin Vertiport'] - 1]
        dest_vrp_id = VERTIPORTS_IDS[departure['Destination Vertiport'] - 1]
        intended_departure_time = departure['Departure Time']
        planned_flight_time = departure['Arrival Time'] - departure['Departure Time']

        schedule_found = False

        while not schedule_found:
            try:
                real_time_departure, real_time_arrival = schedule_flights(vrp_session, orig_vrp_id, intended_departure_time, planned_flight_time, dest_vrp_id)
            except:
                intended_departure_time = intended_departure_time + datetime.timedelta(minutes=DELAY_MIN)
                continue

            schedule_found = True

            # create operational intent for departure
            op_id = departure['ID Departure']
            req = _make_op_request(orig_vrp_id, 0, real_time_departure + datetime.timedelta(seconds=1), real_time_departure + datetime.timedelta(minutes=RESERVATION_TIME_MIN))
            # print("ind: {} intended: {} from: {} to: {} data: {}".format(ind, intended_start_time, time_period[0], time_period[1], data))
            resp = vrp_session.put('/operational_intent_references/{}'.format(op_id), json=req, scope=SCOPE_VRP)
            assert resp.status_code == 200, resp.content

            # create operational intent for arrival
            op_id = departure['ID Arrival']
            req = _make_op_request(dest_vrp_id, 0, real_time_arrival + datetime.timedelta(seconds=1), real_time_arrival + datetime.timedelta(minutes=RESERVATION_TIME_MIN))
            resp = vrp_session.put('/operational_intent_references/{}'.format(op_id), json=req, scope=SCOPE_VRP)
            assert resp.status_code == 200, resp.content


# Ensure Operations do not exist
# Preconditions: none
# Mutations: Operations deleted if exist
def test_final_cleanup(ids, vrp_session):
    test_ensure_clean_workspace(ids, vrp_session)
