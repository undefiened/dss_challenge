"""Basic Constraint tests:

  - make sure the Constraint doesn't exist with get by vertiport id/zone search
  - create the Constraint with a 60 minute length
  - get by vertiport id/zone search
  - get by vertiport id/zone + earliest time search
  - get by vertiport id/zone + lateest time search
  - delete
  - make sure Constraints can't be found by vertiport id/zone search
"""

import datetime
from typing import Literal

from monitoring.monitorlib.testing import assert_datetimes_are_equal
from monitoring.monitorlib.typing import ImplicitDict, StringBasedDateTime
from monitoring.prober.infrastructure import depends_on, register_resource_type
from monitoring.monitorlib.infrastructure import DSSTestSession


import pytest


BASE_URL = 'https://example.com/uss'
CONSTRAINT_TYPE = register_resource_type(1, 'Single constraint')

SCOPE_VRP = 'utm.vertiport_management'


class Time(ImplicitDict):
    ''' A class to hold Time details '''
    value: StringBasedDateTime
    format:Literal['RFC3339']


def make_time(t: datetime) -> Time:
    return Time(value=t.isoformat() + 'Z', format='RFC3339')


def _make_c1_request():
    time_start = datetime.datetime.utcnow()
    time_end = time_start + datetime.timedelta(minutes=60)
    return {
        'vertiport_reservation': {
            'time_start': make_time(time_start),
            'time_end': make_time(time_end),
            'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
            'reserved_zone': 0,
        },
        'old_version': 0,
        'uss_base_url': BASE_URL,
    }


def delete_constraint_reference_if_exists(id: str, vrp_session: DSSTestSession):
    resp = vrp_session.get('/constraint_references/{}'.format(id), scope=SCOPE_VRP)
    if resp.status_code == 200:
        existing_constraint = resp.json().get('constraint_reference', None)
        resp = vrp_session.delete('/constraint_references/{}/{}'.format(id, existing_constraint['ovn']), scope=SCOPE_VRP)
        assert resp.status_code == 200, '{}: {}'.format(resp.url, resp.content)
    elif resp.status_code == 404:
        # As expected.
        pass
    else:
        print(resp.content)
        assert False, resp.content


def test_ensure_clean_workspace(ids, vrp_session):
  delete_constraint_reference_if_exists(ids(CONSTRAINT_TYPE), vrp_session)


# Constraint shouldn't exist by vertiport id/zone search
# Preconditions: None
# Mutations: None
def test_constrain_does_not_exist_query(ids, vrp_session):
  if vrp_session is None:
    return

  resp = vrp_session.post('/constraint_references/query', 
    json = {
        'reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(CONSTRAINT_TYPE) not in [constraints['id'] for constraints in resp.json().get('constraint_references', [])]


# Create Constraint
# Preconditions: None
# Mutations: Constraint created by vrp_session user
@depends_on(test_ensure_clean_workspace)
def test_create_constraint(ids, vrp_session):
  id = ids(CONSTRAINT_TYPE)
  req = _make_c1_request()

  resp = vrp_session.put('/constraint_references/{}'.format(id), json=req, scope=SCOPE_VRP)
  print(resp.content)
  assert resp.status_code == 200, resp.content

  #print(resp.json())
  constraint = resp.json()['constraint_reference']
  assert constraint['id'] == id
  assert constraint['uss_base_url'] == BASE_URL
  assert constraint['uss_availability'] == 'Unknown'
  assert_datetimes_are_equal(constraint['time_start']['value'], req['vertiport_reservation']['time_start']['value'])
  assert_datetimes_are_equal(constraint['time_end']['value'], req['vertiport_reservation']['time_end']['value'])
  assert constraint['version'] == 1


# Preconditions: Constrained created
# Mutations: None
@depends_on(test_create_constraint)
def test_search_vertiport_id_zone(ids, vrp_session):
  resp = vrp_session.post('/constraint_references/query', 
    json = {
        'reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  print(resp.json())
  assert ids(CONSTRAINT_TYPE) in [constraints['id'] for constraints in resp.json().get('constraint_reference', [])]


# Preconditions: Constrained created
# Mutations: None
@depends_on(test_create_constraint)
def test_search_vertiport_id_zone_time(ids, vrp_session):
  time1 = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
  time2 = datetime.datetime.utcnow() + datetime.timedelta(minutes=100)
  
  resp = vrp_session.post('/constraint_references/query', 
    json = {
        'reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': make_time(time1),
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(CONSTRAINT_TYPE) in [x['id'] for x in resp.json().get('constraint_reference', [])]
  
  resp = vrp_session.post('/operational_intent_references/query', 
    json = {
        'reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': make_time(time2),
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(CONSTRAINT_TYPE) in [x['id'] for x in resp.json().get('constraint_reference', [])]

  resp = vrp_session.post('/operational_intent_references/query', 
    json = {
        'reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': make_time(time1),
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(CONSTRAINT_TYPE) in [x['id'] for x in resp.json().get('constraint_reference', [])]

  resp = vrp_session.post('/operational_intent_references/query', 
    json = {
        'reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': make_time(time2),
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(CONSTRAINT_TYPE) in [x['id'] for x in resp.json().get('constraint_reference', [])]

  time3 = time1 +  + datetime.timedelta(minutes=10)
  resp = vrp_session.post('/operational_intent_references/query', 
    json = {
        'reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': make_time(time1),
                'time_end': make_time(time3),
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(CONSTRAINT_TYPE) in [x['id'] for x in resp.json().get('constraint_reference', [])]


@depends_on(test_create_constraint)
def test_delete_constraint(ids, vrp_session):
  id = ids(CONSTRAINT_TYPE)
  resp = vrp_session.get('/constraint_references/{}'.format(id), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  existing_constraint = resp.json().get('constraint_reference', None)
  assert existing_constraint is not None

  req = _make_c1_request()
  req = {
    'key': [existing_constraint["ovn"]],
    'vertiport_reservation': req['vertiport_reservation'],
    'old_version': existing_constraint['version'],
    'uss_base_url': 'https://example.com/uss2'
  }

  ovn = existing_constraint["ovn"]

  resp = vrp_session.delete('/constraint_references/{}/{}'.format(id, ovn), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, "ovn:{}\nresponse: {}".format(ovn, resp.content)


# Constraint shouldn't exist by vertiport id/zone search
# Preconditions: Constraint is deleted
# Mutations: None
@depends_on(test_delete_constraint)
def test_get_deleted_constraint_by_search(ids, vrp_session):
  resp = vrp_session.post('/constraint_references/query',
    json = {
        'reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(CONSTRAINT_TYPE) not in [x['id'] for x in resp.json().get('constraint_reference', [])]


def test_final_cleanup(ids, vrp_session):
    test_ensure_clean_workspace(ids, vrp_session)