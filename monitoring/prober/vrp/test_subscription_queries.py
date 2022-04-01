"""Strategic conflict detection Subscription query tests:

  - add a few Subscriptions spaced in time and vertiport zones
  - query with various combinations of arguments
"""

import datetime
from typing import Dict
from typing import Literal

from monitoring.monitorlib import scd
from monitoring.prober.infrastructure import for_api_versions, register_resource_type

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


def _make_sub_req(time_start, time_end, zone):
  req = {
    'vertiport_reservation': {
            'time_start': make_time(time_start),
            'time_end': make_time(time_end),
            'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
            'vertiport_zone': zone,
        },
    "uss_base_url": "https://example.com/foo",
    "notify_for_operational_intents": True,
    "notify_for_constraints": False,
    'version': 0
  }
  return req


def _make_sub1_req():
  time_start = datetime.datetime.utcnow()
  time_end = time_start + datetime.timedelta(minutes=60)
  
  req = {
    'vertiport_reservation': {
            'time_start': make_time(time_start),
            'time_end': make_time(time_end),
            'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
            'vertiport_zone': 0,
        },
    "uss_base_url": "https://example.com/foo",
    "notify_for_operational_intents": True,
    "notify_for_constraints": False,
    'version': 0
  }
  return req


def _make_sub2_req():
  time_start = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
  time_end = time_start + datetime.timedelta(minutes=60)
  req = {
    'vertiport_reservation': {
            'time_start': make_time(time_start),
            'time_end': make_time(time_end),
            'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
            'vertiport_zone': 1,
        },
    "uss_base_url": "https://example.com/foo",
    "notify_for_operational_intents": True,
    "notify_for_constraints": False
  }
  return req


def _make_sub3_req():
  time_start = datetime.datetime.utcnow() + datetime.timedelta(hours=4)
  time_end = time_start + datetime.timedelta(minutes=60)
  
  req = {
    'vertiport_reservation': {
            'time_start': make_time(time_start),
            'time_end': make_time(time_end),
            'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
            'vertiport_zone': 2,
        },
    "uss_base_url": "https://example.com/foo",
    "notify_for_operational_intents": True,
    "notify_for_constraints": False
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


def test_ensure_clean_workspace(ids, vrp_session):
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
      delete_subscription_if_exists(sub_id, vrp_session)


# Preconditions: No named Subscriptions exist
# Mutations: None
def test_subs_do_not_exist_get(ids, vrp_session):
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
    resp = vrp_session.get('/subscriptions/{}'.format(sub_id), scope=SCOPE_VRP)
    assert resp.status_code == 404, resp.content


# Preconditions: No named Subscriptions exist
# Mutations: None
def test_subs_do_not_exist_query(ids, vrp_session):
  
  resp = vrp_session.post('/subscriptions/query', json=_make_sub1_req(), scope=SCOPE_VRP)
  
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
    assert sub_id not in result_ids
  
  resp = vrp_session.post('/subscriptions/query', json=_make_sub2_req(), scope=SCOPE_VRP)
  
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
    assert sub_id not in result_ids
  
  resp = vrp_session.post('/subscriptions/query', json=_make_sub3_req(), scope=SCOPE_VRP)
  
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
    assert sub_id not in result_ids


# Preconditions: No named Subscriptions exist
# Mutations: Subscriptions 1, 2, and 3 created
def test_create_subs(ids, vrp_session):
  resp = vrp_session.put('/subscriptions/{}'.format(ids(SUB1_TYPE)), json=_make_sub1_req(), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  resp = vrp_session.put('/subscriptions/{}'.format(ids(SUB2_TYPE)), json=_make_sub2_req(), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  resp = vrp_session.put('/subscriptions/{}'.format(ids(SUB3_TYPE)), json=_make_sub3_req(), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content


# Preconditions: Subscriptions 1, 2, and 3 created
# Mutations: None
def test_sub_does_not_exist_query(ids, vrp_session):
  time_start = datetime.datetime.utcnow()
  time_end = time_start + datetime.timedelta(minutes=60)
  
  # another vertiport
  req = {
    'vertiport_reservation': {
            'time_start': make_time(time_start),
            'time_end': make_time(time_end),
            'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10334',
            'vertiport_zone': 0,
        },
    "uss_base_url": "https://example.com/foo",
    "notify_for_operational_intents": True,
    "notify_for_constraints": False,
    'version': 0
  }
  
  resp = vrp_session.post('/subscriptions/query', json=req, scope=SCOPE_VRP)
  
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
    assert sub_id not in result_ids


# Preconditions: Subscriptions 1, 2, and 3 created
# Mutations: None
def test_search_find_all_subs(ids, vrp_session):
  vertiport_req = {
    'vertiport_reservation': {
            'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
        },
  }
  resp = vrp_session.post('/subscriptions/query', json=vertiport_req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
    assert sub_id in result_ids


# Preconditions: Subscriptions 1, 2, and 3 created
# Mutations: None
def test_search_vertiport_zone(ids, vrp_session):
  vertiport_req = {
    'vertiport_reservation': {
            'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
            'vertiport_zone': 0,
        },
  }
  resp = vrp_session.post(
    '/subscriptions/query', json=vertiport_req, scope=SCOPE_VRP)

  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB1_TYPE) in result_ids
  assert ids(SUB2_TYPE) not in result_ids
  assert ids(SUB3_TYPE) not in result_ids


# Preconditions: Subscriptions 1, 2, and 3 created
# Mutations: None
def test_search_time(ids, vrp_session):
  time_start = datetime.datetime.utcnow()
  time_end = time_start + datetime.timedelta(minutes=1)

  resp = vrp_session.post('/subscriptions/query', json=_make_sub_req(time_start, time_end, 0), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB1_TYPE) in result_ids
  assert ids(SUB2_TYPE) not in result_ids
  assert ids(SUB3_TYPE) not in result_ids

  resp = vrp_session.post(
    '/subscriptions/query', json=_make_sub_req(None, time_end), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB1_TYPE) in result_ids
  assert ids(SUB2_TYPE) not in result_ids
  assert ids(SUB3_TYPE) not in result_ids

  time_start = datetime.datetime.utcnow() + datetime.timedelta(hours=4)
  time_end = time_start + datetime.timedelta(minutes=1)

  resp = vrp_session.post(
    '/subscriptions/query', json=_make_sub_req(time_start, time_end, 0), scope=SCOPE_VRP)

  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB1_TYPE) not in result_ids
  assert ids(SUB2_TYPE) not in result_ids
  assert ids(SUB3_TYPE) in result_ids

  resp = vrp_session.post(
    '/subscriptions/query', json=_make_sub_req(time_start, None), scope=SCOPE_VRP)

  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB1_TYPE) not in result_ids
  assert ids(SUB2_TYPE) not in result_ids
  assert ids(SUB3_TYPE) in result_ids


# Preconditions: Subscriptions 1, 2, and 3 created
# Mutations: None
def test_search_time_vertiport_zone(ids, vrp_session):
  time_start = datetime.datetime.utcnow()
  time_end = time_start + datetime.timedelta(hours=2.5)
  
  resp = vrp_session.post(
    '/subscriptions/query', json=_make_sub_req(time_start, time_end, 1), scope=SCOPE_VRP)

  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB1_TYPE) not in result_ids
  assert ids(SUB2_TYPE) in result_ids
  assert ids(SUB3_TYPE) not in result_ids


# Preconditions: Subscriptions 1, 2, and 3 created
# Mutations: Subscriptions 1, 2, and 3 deleted
def test_delete_subs(ids, vrp_session):
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
    resp = vrp_session.get('/subscriptions/{}'.format(sub_id), scope=SCOPE_VRP)
    assert resp.status_code == 200
    resp = vrp_session.delete('/subscriptions/{}/{}'.format(sub_id, resp.json()['subscription']['version']), scope=SCOPE_VRP)

    assert resp.status_code == 200, resp.content


def test_final_cleanup(ids, vrp_session):
    test_ensure_clean_workspace(ids, vrp_session)
