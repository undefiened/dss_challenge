"""Basic multi-Operation tests:
"""

import datetime
from typing import Dict, Tuple
from typing import Literal

from monitoring.monitorlib import scd
#from monitoring.monitorlib.scd import SCOPE_SC
from monitoring.monitorlib.testing import assert_datetimes_are_equal
from monitoring.prober.infrastructure import register_resource_type
from monitoring.monitorlib.infrastructure import DSSTestSession
from monitoring.monitorlib.typing import ImplicitDict, StringBasedDateTime

SCOPE_VRP = 'utm.vertiport_management'

class Time(ImplicitDict):
    ''' A class to hold Time details '''
    value: StringBasedDateTime
    format:Literal['RFC3339']

def make_time(t: datetime) -> Time:
    return Time(value=t.isoformat() + 'Z', format='RFC3339')

URL_OP1 = 'https://example.com/op1/dss'
URL_SUB1 = 'https://example.com/subs1/dss'
URL_OP2 = 'https://example.com/op2/dss'
URL_SUB2 = 'https://example.com/subs2/dss'

OP1_TYPE = register_resource_type(213, 'Operational intent 1')
OP2_TYPE = register_resource_type(214, 'Operational intent 2')
SUB2_TYPE = register_resource_type(215, 'Subscription')


op1_ovn = None
op2_ovn = None

sub2_version = None


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
    'uss_base_url': URL_OP1,
    'new_subscription': {
        'uss_base_url': URL_SUB1,
        'notify_for_constraints': False
    }
  }


def _make_op2_request():
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
    'state': 'Accepted',
    'uss_base_url': URL_OP2,
  }


# Parses `subscribers` response field into Dict[USS base URL, Dict[Subscription ID, Notification index]]
def _parse_subscribers(subscribers: Dict) -> Dict[str, Dict[str, int]]:
  return {to_notify['uss_base_url']: {sub['subscription_id']: sub['notification_index']
                                      for sub in to_notify['subscriptions']}
          for to_notify in subscribers}


# Parses AirspaceConflictResponse entities into Dict[Operation ID, Operation Reference] +
# Dict[Constraint ID, Constraint Reference] + set of OVNs
def _parse_conflicts(entities: Dict) -> Tuple[Dict[str, Dict], Dict[str, Dict], set]:
  ops = {}
  constraints = {}
  ovns = set()
  for entity in entities:
    op = entity.get('operation_reference', None)
    if op is not None:
      ops[op['id']] = op
    constraint = entity.get('constraint', None)
    if constraint is not None:
      constraints[constraint['id']] = constraint
    ovn = entity.get('ovn', None)
    if ovn is not None:
      ovns.add(ovn)
  return ops, constraints, ovns


# Parses AirspaceConflictResponse (v17) entities into Dict[Operation ID, Operation Reference] +
# Dict[Constraint ID, Constraint Reference]
def _parse_conflicts_v17(conflicts: Dict) -> Tuple[Dict[str, Dict], Dict[str, Dict], set]:
  missing_operational_intents = conflicts.get('missing_operational_intents', [])
  ops = {op['id']: op for op in missing_operational_intents}
  missing_constraints = conflicts.get('missing_constraints', [])
  constraints = {constraint['id']: constraint for constraint in missing_constraints}
  ovns = set()
  for entity in missing_constraints + missing_constraints:
    ovn = entity.get('ovn', None)
    if ovn is not None:
      ovns.add(ovn)
  return ops, constraints, ovns


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


def test_ensure_clean_workspace(ids, vrp_session, vrp_session2):
  for op_id, owner in ((ids(OP1_TYPE), vrp_session), (ids(OP2_TYPE), vrp_session2)):
      delete_operation_if_exists(op_id, owner)
  delete_subscription_if_exists(ids(SUB2_TYPE), vrp_session2)


# Op1 shouldn't exist by ID for USS1 when starting this sequence
# Preconditions: None
# Mutations: None
def test_op1_does_not_exist_get_1_v17(ids, vrp_session, vrp_session2):
  resp = vrp_session.get('/operational_intent_references/{}'.format(ids(OP1_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 404, resp.content


# Op1 shouldn't exist by ID for USS2 when starting this sequence
# Preconditions: None
# Mutations: None
def test_op1_does_not_exist_get_2_v17(ids, vrp_session2):
  resp = vrp_session2.get('/operational_intent_references/{}'.format(ids(OP1_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 404, resp.content


# Create Op1 normally from USS1 (also creates implicit Subscription)
# Preconditions: None
# Mutations: Operation Op1 created by vrp_session user

def test_create_op1_v17(ids, vrp_session, vrp_session2):

  id = ids(OP1_TYPE)

  req = _make_op1_request()
  print(req)


  resp = vrp_session.put('/operational_intent_references/{}'.format(id), json=req, scope=SCOPE_VRP)

  print(resp.content)

  assert resp.status_code == 200, resp.content


def test_final_cleanup(ids, vrp_session, vrp_session2):
    test_ensure_clean_workspace(ids, vrp_session, vrp_session2)
