"""Basic Subscription query tests:

  - make sure the Subscription doesn't exist with get by vertiport id/zone search
  - create the Subscription with a 60 minute length
  - get by vertiport id/zone search
  - get by vertiport id/zone + earliest time search
  - get by vertiport id/zone + lateest time search
  - delete
  - make sure Subscription can't be found by vertiport id/zone search
"""

import datetime
from typing import Literal

from monitoring.prober.infrastructure import register_resource_type

from monitoring.monitorlib.typing import ImplicitDict, StringBasedDateTime
from monitoring.monitorlib.infrastructure import DSSTestSession

SCOPE_VRP = 'utm.vertiport_management'

SUB_TYPE = register_resource_type(216, 'Subscription 1')


class Time(ImplicitDict):
    ''' A class to hold Time details '''
    value: StringBasedDateTime
    format:Literal['RFC3339']


def make_time(t: datetime) -> Time:
    return Time(value=t.isoformat() + 'Z', format='RFC3339')


def _make_sub1_req():
  time_start = datetime.datetime.utcnow()
  time_end = time_start + datetime.timedelta(minutes=60)
  
  req = {
      'vertiport_reservation': {
          'time_start': make_time(time_start),
          'time_end': make_time(time_end),
          'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
          'reserved_zone': 0,
      },
      'uss_base_url': "https://example.com/foo",
      'notify_for_constraints': False,
      'notify_for_operational_intents': True,
      'old_version': 0,
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


# Delete Subscription if exists
# Preconditions: None
# Mutations: Subscription deleted if exists
def test_ensure_clean_workspace(ids, vrp_session):
  delete_subscription_if_exists(ids(SUB_TYPE), vrp_session)


# Subscription shouldn't exist by vertiport id/zone search
# Preconditions: None
# Mutations: None
def test_sub_does_not_exist_query(ids, vrp_session):
  if vrp_session is None:
    return

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
  assert ids(SUB_TYPE) not in [x['id'] for x in resp.json().get('subscriptions', [])]


# Create Subscription
# Preconditions: No named Subscription exists
# Mutations: Subscription created
def test_create_sub(ids, vrp_session):
  req = _make_sub1_req()
  
  resp = vrp_session.put('/subscriptions/{}'.format(ids(SUB_TYPE)), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content


# Search Subscription by vertiport id and zone
# Preconditions: Subscription created
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
  assert ids(SUB_TYPE) in [x['id'] for x in resp.json()['subscriptions']]

  resp = vrp_session.post('/subscriptions/query',
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10334',
                'reserved_zone': 1,
            }
        }
    }, scope=SCOPE_VRP)
  
  assert resp.status_code == 200, resp.content
  assert ids(SUB_TYPE) not in [x['id'] for x in resp.json()['subscriptions']]


# Search Subscription by vertiport id, zone + earliest or/and latest time
# Preconditions: Subscription created
# Mutations: None
def test_search_time(ids, vrp_session):
  time1 = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
  time2 = datetime.datetime.utcnow() + datetime.timedelta(minutes=100)
  
  resp = vrp_session.post('/subscriptions/query', 
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': make_time(time1),
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
    }, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB_TYPE) in result_ids
  
  resp = vrp_session.post('/subscriptions/query',
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': make_time(time2),
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
    }, scope=SCOPE_VRP)
  
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB_TYPE) not in result_ids
  
  resp = vrp_session.post('/subscriptions/query',
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': make_time(time1),
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
    }, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB_TYPE) in result_ids
  
  resp = vrp_session.post('/subscriptions/query',
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': make_time(time2),
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
    }, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB_TYPE) not in result_ids
  
  time3 = time1 + datetime.timedelta(minutes=10)
  resp = vrp_session.post('/subscriptions/query',
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': make_time(time1),
                'time_end': make_time(time3),
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
    }, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  result_ids = [x['id'] for x in resp.json()['subscriptions']]
  assert ids(SUB_TYPE) in result_ids


# Delete Subscription
# Preconditions: Subscription created
# Mutations: Subscription deleted
def test_delete_sub(ids, vrp_session):
  resp = vrp_session.get('/subscriptions/{}'.format(ids(SUB_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200
  resp = vrp_session.delete('/subscriptions/{}/{}'.format(ids(SUB_TYPE), resp.json()['subscription']['version']), scope=SCOPE_VRP)

  assert resp.status_code == 200, resp.content


# Subscriptiont shouldn't exist by vertiport id/zone search
# Preconditions: Subscription deleted
# Mutations: None
def test_get_deleted_sub_by_search(ids, vrp_session):
  if vrp_session is None:
    return

  resp = vrp_session.post('/subscriptions/query',
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
    }, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  assert ids(SUB_TYPE) not in [x['id'] for x in resp.json()['subscriptions']]


# Ensure Subscription does not exist
# Preconditions: none
# Mutations: Subscription deleted if exists
def test_final_cleanup(ids, vrp_session):
    test_ensure_clean_workspace(ids, vrp_session)
