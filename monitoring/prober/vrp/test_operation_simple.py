"""Basic Operation tests:

  - make sure the Operation doesn't exist with get by ID
  - create the Operation with a 60 minute length
  - get by ID
  - mutate
  - delete
"""

import datetime
from typing import Literal

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

  req = _make_op1_request()

  resp = vrp_session.put('/operational_intent_references/{}'.format(id), json=req, scope=SCOPE_VRP)

  assert resp.status_code == 200, resp.content


@depends_on(test_create_op)
def test_get_op_by_id(ids, vrp_session):
  resp = vrp_session.get('/operational_intent_references/{}'.format(ids(OP_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  data = resp.json()
  op = data['operational_intent_reference']
  assert op['id'] == ids(OP_TYPE)
  assert op['uss_base_url'] == BASE_URL
  assert op['uss_availability'] == "Unknown"
  assert op['version'] == 1
  assert 'state' in op
  assert op['state'] == 'Accepted', "The response has a state = '{}'".format(data['operational_intent_reference']['state'])


@depends_on(test_create_op)
def test_mutate_op(ids, vrp_session):
  # GET current op
  resp = vrp_session.get('/operational_intent_references/{}'.format(ids(OP_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  existing_op = resp.json().get('operational_intent_reference', None)
  assert existing_op is not None, resp.json()

  req = _make_op1_request()
  req = {
    'key': [existing_op["ovn"]],
    'vertiport_reservation': req['vertiport_reservation'],
    'old_version': existing_op['version'],
    'state': 'Activated',
    'uss_base_url': 'https://example.com/uss2',
    'subscription_id': existing_op['subscription_id']
  }

  resp = vrp_session.put(
    '/operational_intent_references/{}/{}'.format(ids(OP_TYPE), existing_op["ovn"]), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  data = resp.json()
  op = data['operational_intent_reference']
  assert op['id'] == ids(OP_TYPE)
  assert op['uss_base_url'] == 'https://example.com/uss2'
  assert op['version'] == 2
  assert op['subscription_id'] == existing_op['subscription_id']
  assert op['state'] == 'Activated'
  assert op.get('ovn', '')


@depends_on(test_mutate_op)
def test_delete_op(ids, vrp_session):
  resp = vrp_session.get('/operational_intent_references/{}'.format(ids(OP_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  ovn = resp.json()['operational_intent_reference']['ovn']

  resp = vrp_session.delete('/operational_intent_references/{}/{}'.format(ids(OP_TYPE), ovn), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content


@depends_on(test_delete_op)
def test_get_deleted_op_by_id(ids, vrp_session):
  resp = vrp_session.get('/operational_intent_references/{}'.format(ids(OP_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 404, resp.content

def test_final_cleanup(ids, vrp_session):
    test_ensure_clean_workspace(ids, vrp_session)
