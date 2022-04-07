"""

"""

import datetime
from typing import Literal
import pandas as pd

from monitoring.prober.infrastructure import depends_on, register_resource_type
from monitoring.monitorlib.infrastructure import DSSTestSession
from monitoring.monitorlib.typing import ImplicitDict, StringBasedDateTime

SCOPE_VRP = 'utm.vertiport_management'

VRP1_DEPARTURES = []
VRP2_DEPARTURES = []
VRP3_DEPARTURES = []


def read_vrp1_departures():
    filename = "/monitoring/prober/vrp/RandomDemand.xlsx"
    vrp1_departures_df = pd.read_excel(filename, sheet_name='Departure from Vertiport 1', \
        dtype={'Flight ID': str, 'Start Vertiport 1': str, \
        'Destination Vertiport 2': str, 'Destination Vertiport 3': str})
    
    vrp1_departures_list = []

    for idx, row in vrp1_departures_df.iterrows():
        dest_vrp = 2 if not pd.isna(row['Destination Vertiport 2']) else 3
        
        start_datetime_str = row['Start Vertiport 1']
        start_datetime_obj = datetime.datetime.strptime(start_datetime_str, '%Y-%m-%d %H:%M:%S')
        
        end_datetime_str = row['Destination Vertiport 2'] \
            if dest_vrp==2 \
            else row['Destination Vertiport 3']
        
        end_datetime_obj = datetime.datetime.strptime(end_datetime_str, '%Y-%m-%d %H:%M:%S')
        
        start_datetime_obj = start_datetime_obj + datetime.timedelta(days=20)
        end_datetime_obj = end_datetime_obj + datetime.timedelta(days=20)
        
        one_flight_dict = {
            "Flight ID": row['Flight ID'],
            "Destination Vertiport": dest_vrp,
            "Start Time": start_datetime_obj,
            "End Time":  end_datetime_obj
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
        
        start_datetime_str = row['Start Vertiport 2']
        start_datetime_obj = datetime.datetime.strptime(start_datetime_str, '%Y-%m-%d %H:%M:%S')
        
        end_datetime_str = row['Destination Vertiport 1'] \
            if dest_vrp==1 \
            else row['Destination Vertiport 3']
        
        end_datetime_obj = datetime.datetime.strptime(end_datetime_str, '%Y-%m-%d %H:%M:%S')
        
        start_datetime_obj = start_datetime_obj + datetime.timedelta(days=20)
        end_datetime_obj = end_datetime_obj + datetime.timedelta(days=20)

        one_flight_dict = {
            "Flight ID": row['Flight ID'],
            "Destination Vertiport": dest_vrp,
            "Start Time": start_datetime_obj,
            "End Time":  end_datetime_obj
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
        
        start_datetime_str = row['Start Vertiport 3']
        start_datetime_obj = datetime.datetime.strptime(start_datetime_str, '%Y-%m-%d %H:%M:%S')
        
        end_datetime_str = row['Destination Vertiport 1'] \
            if dest_vrp==1 \
            else row['Destination Vertiport 2']
        
        end_datetime_obj = datetime.datetime.strptime(end_datetime_str, '%Y-%m-%d %H:%M:%S')
        
        start_datetime_obj = start_datetime_obj + datetime.timedelta(days=20)
        end_datetime_obj = end_datetime_obj + datetime.timedelta(days=20)

        
        one_flight_dict = {
            "Flight ID": row['Flight ID'],
            "Destination Vertiport": dest_vrp,
            "Start Time": start_datetime_obj,
            "End Time":  end_datetime_obj
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

OP_TYPE = register_resource_type(213, 'Operational intent')


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
    global VRP1_DEPARTURES, VRP2_DEPARTURES, VRP3_DEPARTURES
    VRP1_DEPARTURES = read_vrp1_departures()
    VRP2_DEPARTURES = read_vrp2_departures()
    VRP3_DEPARTURES = read_vrp3_departures()


def test_ensure_clean_workspace(ids, vrp_session):
    delete_operation_if_exists(ids(OP_TYPE), vrp_session)


# Op shouldn't exist by ID
# Preconditions: None
# Mutations: None
def test_op_does_not_exist_get(ids, vrp_session):
  resp = vrp_session.get('/operational_intent_references/{}'.format(ids(OP_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 404, resp.content


# Create Op
# Preconditions: None
# Mutations: Operation Op created by vrp_session user
@depends_on(test_ensure_clean_workspace)
def test_create_op(ids, vrp_session):

  id = ids(OP_TYPE)
  
  vrp1_id = 'ACDE070D-8C4C-4f0D-9d8A-000000000001'
  start_time =  VRP1_DEPARTURES[1]['Start Time']
  end_time = start_time + datetime.timedelta(minutes=2.5)
  
  req = _make_op_request(vrp1_id, 0, start_time, end_time)
  
  resp = vrp_session.put('/operational_intent_references/{}'.format(id), json=req, scope=SCOPE_VRP)
  
  assert resp.status_code == 200, resp.content


@depends_on(test_create_op)
def test_delete_op(ids, vrp_session):
  resp = vrp_session.get('/operational_intent_references/{}'.format(ids(OP_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  ovn = resp.json()['operational_intent_reference']['ovn']

  resp = vrp_session.delete('/operational_intent_references/{}/{}'.format(ids(OP_TYPE), ovn), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content


def test_final_cleanup(ids, vrp_session):
    test_ensure_clean_workspace(ids, vrp_session)
