"""Basic multi-Operation tests:

  - create op1 by uss1
  - create sub2 by uss2
  - use sub2 to create op2 by uss2
  - mutate op1
  - delete op1
  - delete op2
  - delete sub2
"""

import datetime
from typing import Dict, Tuple
from typing import Dict
from typing import Literal

#from monitoring.monitorlib.infrastructure import default_scope
from monitoring.monitorlib import scd
from monitoring.monitorlib.scd import SCOPE_SC
from monitoring.monitorlib.testing import assert_datetimes_are_equal
from monitoring.prober.infrastructure import for_api_versions, register_resource_type
#from monitoring.prober.scd import actions
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
    'extents':
        [{'time_start': make_time(time_start),
         'time_end': make_time(time_end),
         'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
         'vertiport_zone': 0,
        }],
    #'extents': [{'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
    #             'vertiport_zone': 0,
    #             'time_start': {'value': '2022-03-24T23:56:40.026696Z', 'format': 'RFC3339'},
    #             'time_end': {'value': '2022-03-25T00:56:40.026696Z', 'format': 'RFC3339'}
    #             }], 

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
    'extents': {
            'time_start': make_time(time_start),
            'time_end': make_time(time_end),
            'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
            'vertiport_zone': 0,
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
        resp = vrp_session.delete('/operational_intent_references/{}/{}'.format(id, ovn))
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


# Op1 shouldn't exist when searching for USS1 when starting this sequence
# Preconditions: None
# Mutations: None
'''
def test_op1_does_not_exist_query_1_v17(ids, vrp_session, vrp_session2):
  if vrp_session is None:
    return
  time_start = datetime.datetime.utcnow()
  time_end = time_start + datetime.timedelta(hours=1)
  resp = vrp_session.post('/operational_intent_references/query', json={
    'vertiport_reservation': {
            'time_start': make_time(time_start),
            'time_end': make_time(time_end),
            'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
            'vertiport_zone': 0,
        }
  }, scope=SCOPE_VRP )
  assert resp.status_code == 200, resp.content
  assert ids(OP1_TYPE) not in [op['id'] for op in resp.json().get('operational_intent_reference', [])]


# Op1 shouldn't exist when searching for USS2 when starting this sequence
# Preconditions: None
# Mutations: None
def test_op1_does_not_exist_query_2_v17(ids, vrp_session, vrp_session2):
  if vrp_session2 is None:
    return
  time_start = datetime.datetime.utcnow()
  time_end = time_start + datetime.timedelta(hours=1)
  resp = vrp_session2.post('/operational_intent_references/query', json={
    'vertiport_reservation': {
            'time_start': make_time(time_start),
            'time_end': make_time(time_end),
            'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
            'vertiport_zone': 0,
        }
  }, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  assert ids(OP1_TYPE) not in [op['id'] for op in resp.json().get('operational_intent_reference', [])]
'''

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
  
'''
  data = resp.json()
  op = data['operational_intent_reference']
  assert op['id'] == ids(OP1_TYPE)
  assert op['uss_base_url'] == URL_OP1
  assert op['uss_availability'] == "Unknown"
  assert_datetimes_are_equal(op['time_start']['value'], req['vertiport_reservation'][0]['time_start']['value'])
  assert_datetimes_are_equal(op['time_end']['value'], req['vertiport_reservation'][0]['time_end']['value'])
  assert op['version'] == 1
  assert 'subscription_id' in op
  assert op['state'] == 'Accepted'
  assert op.get('ovn', '')

  # Make sure the implicit Subscription exists when queried separately
  resp = vrp_session.get('/subscriptions/{}'.format(op['subscription_id']), scope=SCOPE_VRP)
  

  assert resp.status_code == 200, resp.content

  global op1_ovn
  op1_ovn = op['ovn']
'''

'''
# Try (unsuccessfully) to delete the implicit Subscription
# Preconditions: Operation Op1 created by vrp_session user
# Mutations: None
def test_delete_implicit_sub_v17(ids, vrp_session, vrp_session2):
  if vrp_session is None:
    return
  resp = vrp_session.get('/operational_intent_references/{}'.format(ids(OP1_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  operational_intent_reference = resp.json()['operational_intent_reference']
  implicit_sub_id = operational_intent_reference['subscription_id']
  implicit_sub_version = operational_intent_reference['version']

  resp = vrp_session.delete('/subscriptions/{}/{}'.format(implicit_sub_id, implicit_sub_version), scope=SCOPE_VRP)
  assert resp.status_code == 400, resp.content


# Try (unsuccessfully) to delete Op1 from non-owning USS
# Preconditions: Operation Op1 created by vrp_session user
# Mutations: None
def test_delete_op1_by_uss2_v17(ids, vrp_session, vrp_session2):
  resp = vrp_session2.delete('/operational_intent_references/{}/{}'.format(ids(OP1_TYPE), op1_ovn), scope=SCOPE_VRP)
  assert resp.status_code == 403, resp.content


# Try to create Op2 without specifying a valid Subscription
# Preconditions: Operation Op1 created by vrp_session user
# Mutations: None
def test_create_op2_no_sub_v17(ids, vrp_session, vrp_session2):
  req = _make_op2_request()
  resp = vrp_session2.put('/operational_intent_references/{}'.format(ids(OP2_TYPE)), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 400, resp.content


# Create a Subscription we can use for Op2
# Preconditions: Operation Op1 created by vrp_session user
# Mutations: Subscription Sub2 created by vrp_session2 user
def test_create_op2sub(ids, vrp_session, vrp_session2):
  if vrp_session2 is None:
    return
  time_start = datetime.datetime.utcnow()
  time_end = time_start + datetime.timedelta(minutes=70)
  req = {
    'vertiport_reservation': {
            'time_start': make_time(time_start),
            'time_end': make_time(time_end),
            'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
            'vertiport_zone': 0,
        },
    "uss_base_url": URL_SUB2,
    "notify_for_constraints": False
  }
  req.update({"notify_for_operational_intents": True})

  resp = vrp_session2.put('/subscriptions/{}'.format(ids(SUB2_TYPE)), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  # The Subscription response should mention Op1, but not include its OVN
  data = resp.json()
  ops = data['operational_intent_references']
  assert len(ops) > 0
  op = [op for op in ops if op['id'] == ids(OP1_TYPE)][0]
  assert op.get('ovn', '') in scd.NO_OVN_PHRASES

  assert data['subscription']['notification_index'] == 0

  resp = vrp_session2.get('/subscriptions/{}'.format(ids(SUB2_TYPE)))
  assert resp.status_code == 200, resp.content

  global sub2_version
  sub2_version = data['subscription']['version']


# Try (unsuccessfully) to create Op2 with a missing key
# Preconditions:
#   * Operation Op1 created by vrp_session user
#   * Subscription Sub2 created by vrp_session2 user
# Mutations: None
def test_create_op2_no_key_v17(ids, vrp_session, vrp_session2):
  req = _make_op2_request()
  req['subscription_id'] = ids(SUB2_TYPE)
  resp = vrp_session2.put('/operational_intent_references/{}'.format(ids(OP2_TYPE)), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 409, resp.content
  data = resp.json()
  assert 'missing_operational_intents' in data, data
  missing_ops, _, _ = _parse_conflicts_v17(data)
  assert ids(OP1_TYPE) in missing_ops


# Create Op2 successfully, referencing the pre-existing Subscription
# Preconditions:
#   * Operation Op1 created by vrp_session user
#   * Subscription Sub2 created by vrp_session2 user
# Mutations: Operation Op2 created by vrp_session2 user
def test_create_op2_v17(ids, vrp_session, vrp_session2):
  req = _make_op2_request()
  req['subscription_id'] = ids(SUB2_TYPE)
  req['key'] = [op1_ovn]
  resp = vrp_session2.put('/operational_intent_references/{}'.format(ids(OP2_TYPE)), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  data = resp.json()
  op = data['operational_intent_reference']
  assert op['id'] == ids(OP2_TYPE)
  assert op['uss_base_url'] == URL_OP2
  assert_datetimes_are_equal(op['time_start']['value'], req['vertiport_reservation'][0]['time_start']['value'])
  assert_datetimes_are_equal(op['time_end']['value'], req['vertiport_reservation'][0]['time_end']['value'])
  assert op['version'] == 1
  assert 'subscription_id' in op
  assert op['state'] == 'Accepted'
  assert op.get('ovn', '')

  resp = vrp_session2.get('/operational_intent_references/{}'.format(ids(OP1_TYPE)))
  assert resp.status_code == 200, resp.content
  implicit_sub_id = resp.json()['operational_intent_reference']['subscription_id']

  # USS2 should definitely be instructed to notify USS1's implicit Subscription of the new Operation
  subscribers = _parse_subscribers(data.get('subscribers', []))
  assert URL_SUB1 in subscribers, subscribers
  assert implicit_sub_id in subscribers[URL_SUB1], subscribers[URL_SUB1]

  # USS2 should also be instructed to notify USS2's explicit Subscription of the new Operation
  assert URL_SUB2 in subscribers, subscribers
  assert ids(SUB2_TYPE) in subscribers[URL_SUB2], subscribers[URL_SUB2]
  assert subscribers[URL_SUB2][ids(SUB2_TYPE)] == 1

  global op2_ovn
  op2_ovn = op['ovn']


# Op1 and Op2 should both be visible to USS1, but Op2 shouldn't have an OVN
# Preconditions:
#   * Operation Op1 created by vrp_session user
#   * Operation Op2 created by vrp_session2 user
# Mutations: None
def test_read_ops_from_uss1_v17(ids, vrp_session, vrp_session2):
  if vrp_session is None:
    return
  time_start = datetime.datetime.utcnow()
  time_end = time_start + datetime.timedelta(hours=1)
  resp = vrp_session.post('/operational_intent_references/query', json={
    'vertiport_reservation': {
            'time_start': make_time(time_start),
            'time_end': make_time(time_end),
            'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
            'vertiport_zone': 0,
        }
  }, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  ops = {op['id']: op for op in resp.json().get('operational_intent_references', [])}
  assert ids(OP1_TYPE) in ops
  assert ids(OP2_TYPE) in ops

  ovn1 = ops[ids(OP1_TYPE)].get('ovn', '')
  ovn2 = ops[ids(OP2_TYPE)].get('ovn', '')
  assert ovn1 not in scd.NO_OVN_PHRASES
  assert ovn2 in scd.NO_OVN_PHRASES


# Op1 and Op2 should both be visible to USS2, but Op1 shouldn't have an OVN
# Preconditions:
#   * Operation Op1 created by vrp_session user
#   * Operation Op2 created by vrp_session2 user
# Mutations: None
def test_read_ops_from_uss2_v17(ids, vrp_session, vrp_session2):
  if vrp_session2 is None:
    return
  time_start = datetime.datetime.utcnow()
  time_end = time_start + datetime.timedelta(hours=1)
  resp = vrp_session2.post('/operational_intent_references/query', json={
    'vertiport_reservation': {
            'time_start': make_time(time_start),
            'time_end': make_time(time_end),
            'vertiport_id': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
            'vertiport_zone': 0,
        }
  }, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  ops = {op['id']: op for op in resp.json().get('operational_intent_references', [])}
  assert ids(OP1_TYPE) in ops
  assert ids(OP2_TYPE) in ops

  ovn1 = ops[ids(OP1_TYPE)].get('ovn', '')
  ovn2 = ops[ids(OP2_TYPE)].get('ovn', '')
  assert ovn1 in scd.NO_OVN_PHRASES
  assert ovn2 not in scd.NO_OVN_PHRASES


# Try (unsuccessfully) to mutate Op1 with various bad keys
# Preconditions:
#   * Operation Op1 created by vrp_session user
#   * Operation Op2 created by vrp_session2 user
# Mutations: None
def test_mutate_op1_bad_key_v17(ids, vrp_session, vrp_session2):
  resp = vrp_session.get('/operational_intent_references/{}'.format(ids(OP1_TYPE)))
  assert resp.status_code == 200, resp.content
  existing_op = resp.json().get('operational_intent_reference', None)
  assert existing_op is not None, resp.content

  old_req = _make_op1_request()
  req = {
    'vertiport_reservation': old_req['vertiport_reservation'],
    'old_version': existing_op['version'],
    'state': 'Accepted',
    'uss_base_url': URL_OP1,
    'subscription_id': existing_op['subscription_id']
  }
  resp = vrp_session.put('/operational_intent_references/{}/{}'.format(ids(OP1_TYPE), op1_ovn), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 409, resp.content
  missing_ops, _, _ = _parse_conflicts_v17(resp.json())
  assert ids(OP1_TYPE) in missing_ops
  assert ids(OP2_TYPE) in missing_ops

  req['key'] = [op1_ovn]
  resp = vrp_session.put('/operational_intent_references/{}/{}'.format(ids(OP1_TYPE), op1_ovn), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 409, resp.content
  missing_ops, _, ovns = _parse_conflicts_v17(resp.json())
  assert ids(OP2_TYPE) in missing_ops
  assert not(op2_ovn in ovns)
  assert not(op1_ovn in ovns)

  req['key'] = [op2_ovn]
  resp = vrp_session.put('/operational_intent_references/{}/{}'.format(ids(OP1_TYPE), op1_ovn), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 409, resp.content
  missing_ops, _, ovns = _parse_conflicts_v17(resp.json())
  assert ids(OP1_TYPE) in missing_ops
  assert not(op2_ovn in ovns)


# Successfully mutate Op1
# Preconditions:
#   * Operation Op1 created by vrp_session user
#   * Subscription Sub2 created by vrp_session2 user
#   * Operation Op2 created by vrp_session2 user
# Mutations: Operation Op1 mutated to second version
def test_mutate_op1_v17(ids, vrp_session, vrp_session2):
  resp = vrp_session.get('/operational_intent_references/{}'.format(ids(OP1_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  existing_op = resp.json().get('operational_intent_reference', None, scope=SCOPE_VRP)
  assert existing_op is not None, resp.content

  global op1_ovn

  old_req = _make_op1_request()
  req = {
    'key': [op1_ovn, op2_ovn],
    'vertiport_reservation': old_req['vertiport_reservation'],
    'old_version': existing_op['version'],
    'state': 'Accepted',
    'uss_base_url': URL_OP1,
    'subscription_id': existing_op['subscription_id']
  }
  resp = vrp_session.put('/operational_intent_references/{}/{}'.format(ids(OP1_TYPE), op1_ovn), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  data = resp.json()
  op = data['operational_intent_reference']
  assert op['id'] == ids(OP1_TYPE)
  assert op['uss_base_url'] == URL_OP1
  assert op['version'] == 2
  assert op['subscription_id'] == existing_op['subscription_id']
  assert op['state'] == 'Accepted'
  assert op.get('ovn', '')

  # USS1 should definitely be instructed to notify USS2's Subscription of the updated Operation
  subscribers = _parse_subscribers(data.get('subscribers', []))
  assert URL_SUB2 in subscribers, subscribers
  assert ids(SUB2_TYPE) in subscribers[URL_SUB2], subscribers[URL_SUB2]
  assert subscribers[URL_SUB2][ids(SUB2_TYPE)] == 2

  op1_ovn = op['ovn']


# Try (unsuccessfully) to delete the stand-alone Subscription that Op2 is relying on
# Preconditions:
#   * Subscription Sub2 created by vpr_session2 user
#   * Operation Op2 created by vpr_session2 user
# Mutations: None
def test_delete_dependent_sub(ids, vrp_session, vrp_session2):
  if vrp_session2 is None:
    return
  resp = vrp_session2.delete('/subscriptions/{}/{}'.format(ids(SUB2_TYPE), sub2_version), scope=SCOPE_VRP)
  assert resp.status_code == 400, resp.content


# Mutate the stand-alone Subscription
# Preconditions:
#   * Operation Op1 created by vrp_session user
#   * Subscription Sub2 created by vrp_session2 user
#   * Operation Op2 created by vrp_session2 user
# Mutations: Subscription Sub2 mutated
def test_mutate_sub2(ids, vrp_session, vrp_session2):
  if vrp_session2 is None:
    return
  time_now = datetime.datetime.utcnow()
  time_start = time_now - datetime.timedelta(minutes=1)
  time_end = time_now + datetime.timedelta(minutes=61)

  # Create a good mutation request
  req = _make_op2_request()
  req['uss_base_url'] = URL_SUB2
  req['vertiport_reservation'] = req['vertiport_reservation'][0]
  del req['state']
  req['notify_for_constraints'] = False
  req['vertiport_reservation']['time_start'] = make_time(time_start)
  req['vertiport_reservation']['time_end'] = make_time(time_end)

  req['notify_for_operational_intents'] = False
  resp = vrp_session2.put('/subscriptions/{}'.format(ids(SUB2_TYPE)), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 400, resp.content
  req['notify_for_operational_intents'] = True

  # Attempt mutation with start time that doesn't cover Op2

  req['vertiport_reservation']['time_start'] = make_time(time_now + datetime.timedelta(minutes=5))
  resp = vrp_session2.put('/subscriptions/{}/{}'.format(ids(SUB2_TYPE), sub2_version), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 400, resp.content
  req['vertiport_reservation']['time_start'] = make_time(time_start)

  # Attempt mutation with end time that doesn't cover Op2
  req['vertiport_reservation']['time_end'] = make_time(time_now)
  resp = vrp_session2.put('/subscriptions/{}/{}'.format(ids(SUB2_TYPE), sub2_version), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 400, resp.content
  req['vertiport_reservation']['time_end'] = make_time(time_end)

  # Attempt mutation without notifying for Operations
  # Perform a valid mutation
  resp = vrp_session2.put('/subscriptions/{}/{}'.format(ids(SUB2_TYPE), sub2_version), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  # The Subscription response should mention Op1 and Op2, but not include Op1's OVN
  data = resp.json()
  ops = {op['id']: op for op in data['operational_intent_references']}
  assert len(ops) >= 2
  assert ops[ids(OP1_TYPE)].get('ovn', '') in scd.NO_OVN_PHRASES
  assert ops[ids(OP2_TYPE)].get('ovn', '') not in scd.NO_OVN_PHRASES

  assert data['subscription']['notification_index'] == 2

  # Make sure the Subscription is still retrievable specifically
  resp = vrp_session2.get('/subscriptions/{}'.format(ids(SUB2_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content


# Delete Op1
# Preconditions:
#   * Subscription Sub2 created/mutated by vrp_session2 user
#   * Operation Op2 created by vrp_session2 user
# Mutations: Operation Op1 deleted
def test_delete_op1_v17(ids, vrp_session, vrp_session2):
  resp = vrp_session.delete('/operational_intent_references/{}/{}'.format(ids(OP1_TYPE), op1_ovn))
  assert resp.status_code == 200, resp.content

  data = resp.json()
  op = data['operational_intent_reference']

  # USS1 should be instructed to notify USS2's Subscription of the deleted Operation
  subscribers = _parse_subscribers(data.get('subscribers', []))
  assert URL_SUB2 in subscribers, subscribers
  assert ids(SUB2_TYPE) in subscribers[URL_SUB2], subscribers[URL_SUB2]
  assert subscribers[URL_SUB2][ids(SUB2_TYPE)] == 3

  resp = vrp_session.get('/subscriptions/{}'.format(op['subscription_id']))
  print(resp.content)
  assert resp.status_code == 404, resp.content


# Delete Op2
# Preconditions:
#   * Operation Op1 deleted
#   * Subscription Sub2 created/mutated by vrp_session2 user
#   * Operation Op2 created by vrp_session2 user
# Mutations: Operation Op2 deleted
def test_delete_op2_v17(ids, vrp_session, vrp_session2):
  resp = vrp_session2.delete('/operational_intent_references/{}/{}'.format(ids(OP2_TYPE), op2_ovn))
  assert resp.status_code == 200, resp.content

  data = resp.json()
  op = data['operational_intent_reference']
  assert op['subscription_id'] == ids(SUB2_TYPE)

  # USS2 should be instructed to notify Sub2 of the deleted Operation
  subscribers = _parse_subscribers(data.get('subscribers', []))
  assert URL_SUB2 in subscribers, subscribers
  assert ids(SUB2_TYPE) in subscribers[URL_SUB2], subscribers[URL_SUB2]
  assert subscribers[URL_SUB2][ids(SUB2_TYPE)] == 4

  resp = vrp_session2.get('/subscriptions/{}'.format(ids(SUB2_TYPE)))
  assert resp.status_code == 200, resp.content


# Delete Subscription used to serve Op2
# Preconditions:
#   * Operation Op1 deleted
#   * Subscription Sub2 created/mutated by vrp_session2 user
#   * Operation Op2 deleted
# Mutations: Subscription Sub2 deleted
def test_delete_sub2(ids, vrp_session2):
  if vrp_session2 is None:
    return
  resp = vrp_session2.delete('/subscriptions/{}/{}'.format(ids(SUB2_TYPE), sub2_version))
  assert resp.status_code == 200, resp.content
'''

def test_final_cleanup(ids, vrp_session, vrp_session2):
    test_ensure_clean_workspace(ids, vrp_session, vrp_session2)
