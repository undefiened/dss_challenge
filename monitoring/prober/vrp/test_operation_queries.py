"""Basic Operation query tests:

  - make sure the Operation doesn't exist with get by vertiport id/zone search
  - create the Operation with a 60 minute length
  - get by vertiport id/zone search
  - get by vertiport id/zone + earliest time search
  - get by vertiport id/zone + lateest time search
  - delete
  - make sure Operation can't be found by vertiport id/zone search
"""

import datetime
from typing import Literal

from monitoring.monitorlib.testing import assert_datetimes_are_equal
from monitoring.prober.infrastructure import depends_on, register_resource_type
from monitoring.monitorlib.infrastructure import DSSTestSession
from monitoring.monitorlib.typing import ImplicitDict, StringBasedDateTime

SCOPE_VRP = 'utm.vertiport_management'

class Time(ImplicitDict):
    ''' A class to hold Time details '''
    value: StringBasedDateTime
    format:Literal['RFC3339']

def make_time(t: datetime) -> Time:
    return Time(value=t.isoformat() + 'Z', format='RFC3339')

BASE_URL = 'https://example.com/uss'

OP_TYPE = register_resource_type(213, 'Operational intent')


def _make_op1_request():
  time_start = datetime.datetime.utcnow() + datetime.timedelta(minutes=20)
  time_end = time_start + datetime.timedelta(minutes=60)

  return {
    'vertiport_reservation':
        {'time_start': make_time(time_start),
         'time_end': make_time(time_end),
         'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
         'reserved_zone': 0,
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


def test_ensure_clean_workspace(ids, vrp_session):
    delete_operation_if_exists(ids(OP_TYPE), vrp_session)


# Op shouldn't exist by vertiport id/zone search
# Preconditions: None
# Mutations: None
def test_op_does_not_exist_query(ids, vrp_session):
  if vrp_session is None:
    return

  resp = vrp_session.post('/operational_intent_references/query', 
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(OP_TYPE) not in [op['id'] for op in resp.json().get('operational_intent_reference', [])]


# Create Op
# Preconditions: None
# Mutations: Operation Op created by vrp_session user
@depends_on(test_ensure_clean_workspace)
def test_create_op(ids, vrp_session):

  id = ids(OP_TYPE)

  req = _make_op1_request()

  resp = vrp_session.put('/operational_intent_references/{}'.format(id), json=req, scope=SCOPE_VRP)

  assert resp.status_code == 200, resp.content

  data = resp.json()
  print(data)
  op = data['operational_intent_reference']
  assert op['id'] == ids(OP_TYPE)
  assert op['uss_base_url'] == BASE_URL
  assert op['uss_availability'] == "Unknown"
  assert_datetimes_are_equal(op['time_start']['value'], req['vertiport_reservation']['time_start']['value'])
  assert_datetimes_are_equal(op['time_end']['value'], req['vertiport_reservation']['time_end']['value'])
  assert op['version'] == 1
  assert 'subscription_id' in op
  assert op['state'] == 'Accepted'
  assert op.get('ovn', '')

  # Make sure the implicit Subscription exists when queried separately
  resp = vrp_session.get('/subscriptions/{}'.format(op['subscription_id']), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content


# Preconditions: Operation created
# Mutations: None
@depends_on(test_create_op)
def test_search_vertiport_id_zone(ids, vrp_session):
  resp = vrp_session.post('/operational_intent_references/query', 
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(OP_TYPE) in [op['id'] for op in resp.json().get('operational_intent_reference', [])]


# Preconditions: Operation created
# Mutations: None
@depends_on(test_create_op)
def test_search_vertiport_id_zone_time(ids, vrp_session):
  time1 = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
  time2 = datetime.datetime.utcnow() + datetime.timedelta(minutes=100)
  
  resp = vrp_session.post('/operational_intent_references/query', 
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': make_time(time1),
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(OP_TYPE) in [op['id'] for op in resp.json().get('operational_intent_reference', [])]
  
  resp = vrp_session.post('/operational_intent_references/query', 
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': make_time(time2),
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(OP_TYPE) not in [op['id'] for op in resp.json().get('operational_intent_reference', [])]

  resp = vrp_session.post('/operational_intent_references/query', 
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': make_time(time1),
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(OP_TYPE) in [op['id'] for op in resp.json().get('operational_intent_reference', [])]

  resp = vrp_session.post('/operational_intent_references/query', 
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': make_time(time2),
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(OP_TYPE) not in [op['id'] for op in resp.json().get('operational_intent_reference', [])]

  time3 = time1 +  + datetime.timedelta(minutes=10)
  resp = vrp_session.post('/operational_intent_references/query', 
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': make_time(time1),
                'time_end': make_time(time3),
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(OP_TYPE) in [op['id'] for op in resp.json().get('operational_intent_reference', [])]


@depends_on(test_create_op)
def test_delete_op(ids, vrp_session):
  resp = vrp_session.get('/operational_intent_references/{}'.format(ids(OP_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  ovn = resp.json()['operational_intent_reference']['ovn']

  resp = vrp_session.delete('/operational_intent_references/{}/{}'.format(ids(OP_TYPE), ovn), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content


# Op shouldn't exist by vertiport id/zone search
# Preconditions: op is deleted
# Mutations: None
@depends_on(test_delete_op)
def test_get_deleted_op_by_search(ids, vrp_session):
  resp = vrp_session.post('/operational_intent_references/query',
    json = {
        'vertiport_reservation_of_interest': {
            'vertiport_reservation': {
                'time_start': None,
                'time_end': None,
                'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
                'reserved_zone': 0,
            }
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(OP_TYPE) not in [op['id'] for op in resp.json().get('operational_intent_reference', [])]


def test_final_cleanup(ids, vrp_session):
    test_ensure_clean_workspace(ids, vrp_session)
