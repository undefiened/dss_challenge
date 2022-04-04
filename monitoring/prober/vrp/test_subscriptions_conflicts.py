"""Basic Subscription query tests:

  - add a few Subscriptions spaced in time
  - query with various combinations of arguments
"""

import datetime
from typing import Dict
from typing import Literal, Optional

#from monitoring.monitorlib import scd
from monitoring.prober.infrastructure import register_resource_type

from monitoring.monitorlib.typing import ImplicitDict, StringBasedDateTime
from monitoring.monitorlib.infrastructure import DSSTestSession

SCOPE_VRP = 'utm.vertiport_management'


SUB1_TYPE = register_resource_type(216, 'Subscription 1')
SUB2_TYPE = register_resource_type(217, 'Subscription 2')
SUB3_TYPE = register_resource_type(218, 'Subscription 3')


class Time(ImplicitDict):
    ''' A class to hold Time details '''
    value: StringBasedDateTime
    format:Literal['RFC3339']


def make_time(t: datetime) -> Time:
    return Time(value=t.isoformat() + 'Z', format='RFC3339')


def _make_sub_req(time_start, time_end, vertiport_id, vertiport_zone):
  time_start = datetime.datetime.utcnow()
  time_end = time_start + datetime.timedelta(minutes=60)
  
  req = {
    'vertiport_reservation': {
        'time_start': make_time(time_start),
        'time_end': make_time(time_end),
        'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
        'reserved_zone': 0,
    },
    'uss_base_url': 'https://example.com/foo',
    'notify_for_operational_intents': True,
    'notify_for_constraints': False,
    'version': 0
  }
  return req


def delete_subscription_if_exists(sub_id: str, vrp_session: DSSTestSession):
    resp = vrp_session.get('/subscriptions/{}'.format(sub_id), scope=SCOPE_VRP)
    if resp.status_code == 200:

        sub = resp.json().get('subscription', None)
        resp = vrp_session.delete('/subscriptions/{}/{}'.format(sub_id, sub['version']), scope=SCOPE_VRP)
        assert resp.status_code == 200, resp.content
    elif resp.status_code == 404:
        # As expected.
        pass
    else:
        assert False, resp.content


# Delete all Subscriptions if exist
# Preconditions: None
# Mutations: Subscriptions deleted if exist
def test_ensure_clean_workspace(ids, vrp_session):
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
      delete_subscription_if_exists(sub_id, vrp_session)


# Subscriptions shouldn't exist by vertiport id/zone search
# Preconditions: None
# Mutations: None
def test_subs_do_not_exist_query(ids, vrp_session):
  req = {
      'vertiport_reservation_of_interest': _make_sub_req(None, None, 'ACDE070D-8C4C-4f0D-9d8A-162843c10333', 0)
  }
  resp = vrp_session.post('/subscriptions/query', json=req, scope=SCOPE_VRP)
  
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]  
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
    assert sub_id not in result_ids


# Create Subscriptions
# Preconditions: No named Subscriptions exist
# Mutations: Subscriptions 1, 2, and 3 created
def test_create_subs(ids, vrp_session):
  time_now =  datetime.datetime.utcnow()
  time_start = time_now
  time_end = time_start + datetime.timedelta(hours=2)
  req = _make_sub_req(time_start, time_end, 'ACDE070D-8C4C-4f0D-9d8A-162843c10333', 0)
  
  resp = vrp_session.put('/subscriptions/{}'.format(ids(SUB1_TYPE)), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  time_start = time_now + datetime.timedelta(hours=1)
  time_end = time_start + datetime.timedelta(hours=2)
  req  = _make_sub_req(time_start, time_end, 'ACDE070D-8C4C-4f0D-9d8A-162843c10333', 0)
  
  resp = vrp_session.put('/subscriptions/{}'.format(ids(SUB2_TYPE)), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  time_start = time_now + datetime.timedelta(hours=2)
  time_end = time_start + datetime.timedelta(hours=1)
  req = _make_sub_req(time_start, time_end, 'ACDE070D-8C4C-4f0D-9d8A-162843c10333', 0)
  
  resp = vrp_session.put('/subscriptions/{}'.format(ids(SUB3_TYPE)), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content


# Search Subscriptions by vertiport id and zone
# Preconditions: Subscriptions 1, 2, and 3 created
# Mutations: None
def test_search_vertiport_id_zone(ids, vrp_session):
  resp = vrp_session.post('/subscriptions/query',
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
    }, scope=SCOPE_VRP)
  
  assert resp.status_code == 200, resp.content

  result_ids = [x['id'] for x in resp.json()['subscriptions']]

  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
    assert sub_id in result_ids


# Search Subscriptions by vertiport id, zone + earliest and latest time
# Preconditions: Subscriptions 1, 2, and 3 created
# Mutations: None
def test_search_time(ids, vrp_session):
  time_start = datetime.datetime.utcnow()
  time_end = time_start + datetime.timedelta(minutes=30)
  
  resp = vrp_session.post('/subscriptions/query', 
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': make_time(time_start),
                'time_end': make_time(time_end),
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
    }, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB1_TYPE) in result_ids
  assert ids(SUB2_TYPE) not in result_ids
  assert ids(SUB3_TYPE) not in result_ids
  
  time_start = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
  time_end = time_start + datetime.timedelta(minutes=30)
  
  resp = vrp_session.post('/subscriptions/query',
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': make_time(time_start),
                'time_end': make_time(time_end),
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
    }, scope=SCOPE_VRP)
  
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB1_TYPE) in result_ids
  assert ids(SUB2_TYPE) in result_ids
  assert ids(SUB3_TYPE) not in result_ids
  
  time_start = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
  time_end = time_start + datetime.timedelta(minutes=30)
  
  resp = vrp_session.post('/subscriptions/query',
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': make_time(time_start),
                'time_end': make_time(time_end),
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
    }, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB1_TYPE) not in result_ids
  assert ids(SUB2_TYPE) in result_ids
  assert ids(SUB3_TYPE) in result_ids


# Delete Subscriptions
# Preconditions: Subscriptions 1, 2, and 3 created
# Mutations: Subscriptions 1, 2, and 3 deleted
def test_delete_subs(ids, vrp_session):
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
    resp = vrp_session.get('/subscriptions/{}'.format(sub_id), scope=SCOPE_VRP)
    assert resp.status_code == 200
    resp = vrp_session.delete('/subscriptions/{}/{}'.format(sub_id, resp.json()['subscription']['version']), scope=SCOPE_VRP)

    assert resp.status_code == 200, resp.content


# Subscriptions shouldn't exist by vertiport id/zone search
# Preconditions: Subscriptions deleted
# Mutations: None
def test_get_deleted_subs_by_search(ids, vrp_session):
  if vrp_session is None:
    return

  resp = vrp_session.post('/subscriptions/query',
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10334',
                'reserved_zone': 1,
            }
        }
    }, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
    assert sub_id not in result_ids


# Ensure Subscriptions do not exist
# Preconditions: none
# Mutations: Subscriptions deleted if exist
def test_final_cleanup(ids, vrp_session):
    test_ensure_clean_workspace(ids, vrp_session)
