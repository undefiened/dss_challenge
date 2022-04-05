"""Basic Constraint-Subscription interaction tests:

  - make sure the Constraint doesn't exist with get by ID
  - create the Constraint with a 60 minute length
  - get by ID
  - search with earliest_time and latest_time
  - mutate
  - delete
"""

import datetime
from typing import Dict, Literal

#from monitoring.monitorlib import scd
from monitoring.prober.infrastructure import register_resource_type

from monitoring.monitorlib.typing import ImplicitDict, StringBasedDateTime
from monitoring.monitorlib.infrastructure import DSSTestSession

SCOPE_VRP = 'utm.vertiport_management'

CONSTRAINT_BASE_URL_1 = 'https://example.com/con1/uss'
CONSTRAINT_BASE_URL_2 = 'https://example.com/con2/uss'
CONSTRAINT_BASE_URL_3 = 'https://example.com/con3/uss'
SUB_BASE_URL_A = 'https://example.com/sub1/uss'
SUB_BASE_URL_B = 'https://example.com/sub2/uss'

CONSTRAINT_TYPE = register_resource_type(2, 'Single constraint')
SUB1_TYPE = register_resource_type(3, 'Constraint subscription 1')
SUB2_TYPE = register_resource_type(4, 'Constraint subscription 2')
SUB3_TYPE = register_resource_type(5, 'Constraint subscription 3')

c1_ovn = None

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
        'uss_base_url': CONSTRAINT_BASE_URL_1,
    }


def _make_sub_req(base_url: str, notify_ops: bool, notify_constraints: bool) -> Dict:
  time_start = datetime.datetime.utcnow()
  time_end = time_start + datetime.timedelta(minutes=60)
  return {
    'vertiport_reservation': {
            'time_start': make_time(time_start),
            'time_end': make_time(time_end),
            'vertiportid': 'ACDE070D-8C4C-4f0D-9d8A-162843c10333',
            'reserved_zone': 0,
        },
    "old_version": 0,
    "uss_base_url": base_url,
    "notify_for_operational_intents": notify_ops,
    "notify_for_constraints": notify_constraints
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
  delete_constraint_reference_if_exists(ids(CONSTRAINT_TYPE), vrp_session)
  
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
    delete_subscription_if_exists(sub_id, vrp_session2)


# Preconditions: None
# Mutations: None
def test_subs_do_not_exist(ids, vrp_session, vrp_session2):
  if vrp_session is None:
    return
  
  resp = vrp_session.get('/subscriptions/{}'.format(ids(SUB1_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 404, resp.content
  resp = vrp_session.get('/subscriptions/{}'.format(ids(SUB2_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 404, resp.content
  resp = vrp_session.get('/subscriptions/{}'.format(ids(SUB3_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 404, resp.content


# Preconditions: None
# Mutations: {Sub1, Sub2, Sub3} created by vrp_session2 user
def test_create_subs(ids, vrp_session, vrp_session2):
  if vrp_session2 is None:
    return

  req = _make_sub_req(SUB_BASE_URL_A, notify_ops=True, notify_constraints=False)
  resp = vrp_session2.put('/subscriptions/{}'.format(ids(SUB1_TYPE)), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  req = _make_sub_req(SUB_BASE_URL_B, notify_ops=False, notify_constraints=True)
  resp = vrp_session2.put('/subscriptions/{}'.format(ids(SUB2_TYPE)), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  req = _make_sub_req(SUB_BASE_URL_B, notify_ops=True, notify_constraints=True)
  resp = vrp_session2.put('/subscriptions/{}'.format(ids(SUB3_TYPE)), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content


# Preconditions: None
# Mutations: None
def test_constraint_does_not_exist(ids, vrp_session, vrp_session2):
  resp = vrp_session.get('/constraint_references/{}'.format(ids(CONSTRAINT_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 404, resp.content


# Preconditions: {Sub1, Sub2, Sub3} created by vrp_session2 user
# Mutations: Constraint ids(CONSTRAINT_ID) created by vrp_session user
def test_create_constraint(ids, vrp_session, vrp_session2):
  id = ids(CONSTRAINT_TYPE)
  req = _make_c1_request()

  resp = vrp_session.put('/constraint_references/{}'.format(id), json=req, scope=SCOPE_VRP)
  print(resp.content)
  assert resp.status_code == 200, resp.content

  data = resp.json()
  
  subscribers = data['subscribers']
  
  assert SUB_BASE_URL_A not in [subscriber['uss_base_url'] for subscriber in subscribers], subscribers
  subscriberb = [subscriber for subscriber in subscribers if subscriber['uss_base_url'] == SUB_BASE_URL_B]
  assert len(subscriberb) == 1, subscribers
  subscriberb = subscriberb[0]
  assert ids(SUB2_TYPE) in [subscription['subscription_id'] for subscription in subscriberb['subscriptions']]
  assert ids(SUB3_TYPE) in [subscription['subscription_id'] for subscription in subscriberb['subscriptions']]
  sub2_index = [subscription['notification_index'] for subscription in subscriberb['subscriptions']
                if subscription['subscription_id'] == ids(SUB2_TYPE)][0]
  assert sub2_index == 1, subscriberb
  sub3_index = [subscription['notification_index'] for subscription in subscriberb['subscriptions']
                if subscription['subscription_id'] == ids(SUB3_TYPE)][0]
  assert sub3_index == 1, subscriberb
  
  global c1_ovn
  c1_ovn = data['constraint_reference']['ovn']


# Preconditions:
#   * Sub1 created by vrp_session2 user
#   * {Sub2, Sub3} received one notification
#   * Constraint ids(CONSTRAINT_ID) created by vrp_session user
# Mutations: Constraint ids(CONSTRAINT_ID) mutated to second version
def test_mutate_constraint(ids, vrp_session, vrp_session2):
  id = ids(CONSTRAINT_TYPE)
  # GET current constraint
  resp = vrp_session.get('/constraint_references/{}'.format(id), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  existing_constraint = resp.json().get('constraint_reference', None)
  assert existing_constraint is not None
  
  req = _make_c1_request()
  req = {
    'key': [existing_constraint["ovn"]],
    'vertiport_reservation': req['vertiport_reservation'],
    'old_version': existing_constraint['version'],
    'uss_base_url': CONSTRAINT_BASE_URL_2
  }
  
  ovn = existing_constraint["ovn"]
  
  resp = vrp_session.put('/constraint_references/{}/{}'.format(id, ovn), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, "ovn:{}\nresponse: {}".format(ovn, resp.content)
  
  data = resp.json()
  subscribers = data['subscribers']
  assert SUB_BASE_URL_A not in [subscriber['uss_base_url'] for subscriber in subscribers], subscribers
  subscriberb = [subscriber for subscriber in subscribers if subscriber['uss_base_url'] == SUB_BASE_URL_B]
  assert len(subscriberb) == 1, subscribers
  subscriberb = subscriberb[0]
  assert ids(SUB2_TYPE) in [subscription['subscription_id'] for subscription in subscriberb['subscriptions']]
  assert ids(SUB3_TYPE) in [subscription['subscription_id'] for subscription in subscriberb['subscriptions']]
  sub2_index = [subscription['notification_index'] for subscription in subscriberb['subscriptions']
                if subscription['subscription_id'] == ids(SUB2_TYPE)][0]
  assert sub2_index == 2, subscriberb
  sub3_index = [subscription['notification_index'] for subscription in subscriberb['subscriptions']
                if subscription['subscription_id'] == ids(SUB3_TYPE)][0]
  assert sub3_index == 2, subscriberb


# Preconditions: {Sub1, Sub2, Sub3} created by vrp_session2 user
# Mutations: Sub1 listens for Constraints, Sub3 doesn't listen for Constraints
def test_mutate_subs(ids, vrp_session2, vrp_session):
  # GET current sub1 before mutation
  resp = vrp_session2.get('/subscriptions/{}'.format(ids(SUB1_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  existing_sub = resp.json().get('subscription', None)
  assert existing_sub is not None

  req = _make_sub_req(SUB_BASE_URL_A, notify_ops=True, notify_constraints=True)
  req['old_version'] = existing_sub['version']
  resp = vrp_session2.put('/subscriptions/{}/{}'.format(ids(SUB1_TYPE), existing_sub['version']), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  data = resp.json()
  print(data)
  assert ids(CONSTRAINT_TYPE) in [constraint['id'] for constraint in data['constraint_references']], data

  # GET current sub3 before mutation
  resp = vrp_session2.get('/subscriptions/{}'.format(ids(SUB3_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  existing_sub = resp.json().get('subscription', None)
  assert existing_sub is not None

  req = _make_sub_req(SUB_BASE_URL_B, notify_ops=True, notify_constraints=False)
  req['old_version'] = existing_sub['version']
  resp = vrp_session2.put('/subscriptions/{}/{}'.format(ids(SUB3_TYPE), existing_sub['version']), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  data = resp.json()
  assert not data['constraint_references'], data


# Preconditions:
#   * Sub1 mutated by vrp_session2 user to receive Constraints
#   * Sub2 received one notification
#   * Sub3 received one notification and mutated by vrp_session2 user to not receive Constraints
#   * Constraint ids(CONSTRAINT_ID) mutated by vrp_session user to second version
# Mutations: Constraint ids(CONSTRAINT_ID) mutated to third version
def test_mutate_constraint2(ids, vrp_session, vrp_session2):
  # GET current constraint
  resp = vrp_session.get('/constraint_references/{}'.format(ids(CONSTRAINT_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  existing_constraint = resp.json().get('constraint_reference', None)
  assert existing_constraint is not None
  
  req = _make_c1_request()
  req = {
    'key': [existing_constraint['ovn']],
    'vertiport_reservation': req['vertiport_reservation'],
    'old_version': existing_constraint['version'],
    'uss_base_url': CONSTRAINT_BASE_URL_3
  }
  
  ovn = existing_constraint["ovn"]
  
  resp = vrp_session.put('/constraint_references/{}/{}'.format(ids(CONSTRAINT_TYPE), ovn), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  
  data = resp.json()
  subscribers = data['subscribers']
  
  subscribera = [subscriber for subscriber in subscribers if subscriber['uss_base_url'] == SUB_BASE_URL_A]
  assert len(subscribera) == 1, subscribers
  subscribera = subscribera[0]
  subscribera_subscriptions = [subscription['subscription_id'] for subscription in subscribera['subscriptions']]
  assert ids(SUB1_TYPE) in subscribera_subscriptions
  assert ids(SUB2_TYPE) not in subscribera_subscriptions
  assert ids(SUB3_TYPE) not in subscribera_subscriptions
  sub1_index = [subscription['notification_index'] for subscription in subscribera['subscriptions']
                if subscription['subscription_id'] == ids(SUB1_TYPE)][0]
  assert sub1_index == 1, subscribera
  
  subscriberb = [subscriber for subscriber in subscribers if subscriber['uss_base_url'] == SUB_BASE_URL_B]
  assert len(subscriberb) == 1, subscribers
  subscriberb = subscriberb[0]
  subscriberb_subscriptions = [subscription['subscription_id'] for subscription in subscriberb['subscriptions']]
  assert ids(SUB1_TYPE) not in subscriberb_subscriptions
  assert ids(SUB2_TYPE) in subscriberb_subscriptions
  assert ids(SUB3_TYPE) not in subscriberb_subscriptions
  sub2_index = [subscription['notification_index'] for subscription in subscriberb['subscriptions']
                if subscription['subscription_id'] == ids(SUB2_TYPE)][0]
  assert sub2_index == 3, subscriberb


# Preconditions: Constraint ids(CONSTRAINT_ID) mutated to second version
# Mutations: Constraint ids(CONSTRAINT_ID) deleted
#def test_delete_constraint(ids, vrp_session, vrp_session2):
#  resp = vrp_session.delete('/constraint_references/{}'.format(ids(CONSTRAINT_TYPE)), scope=SCOPE_VRP)
#  assert resp.status_code == 200, resp.content
def test_delete_constraint(ids, vrp_session, vrp_session2):
  id = ids(CONSTRAINT_TYPE)
  resp = vrp_session.get('/constraint_references/{}'.format(id), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  existing_constraint = resp.json().get('constraint_reference', None)
  assert existing_constraint is not None
  
  ovn = existing_constraint["ovn"]
  
  resp = vrp_session.delete('/constraint_references/{}/{}'.format(id, ovn), scope=SCOPE_VRP)
  assert resp.status_code == 200, "ovn:{}\nresponse: {}".format(ovn, resp.content)


# Preconditions: {Sub1, Sub2, Sub3} created by vrp_session2 user
# Mutations: {Sub1, Sub2, Sub3} deleted
def test_delete_subs(ids, vrp_session2, vrp_session):
  if vrp_session2 is None:
    return
  for sub_id in (ids(SUB1_TYPE), ids(SUB2_TYPE), ids(SUB3_TYPE)):
    resp = vrp_session2.get('/subscriptions/{}'.format(sub_id), scope=SCOPE_VRP)
    assert resp.status_code == 200, resp.content
    sub = resp.json().get('subscription', None)
    resp = vrp_session2.delete('/subscriptions/{}/{}'.format(sub_id, sub['version']), scope=SCOPE_VRP)
    assert resp.status_code == 200, resp.content


def test_final_cleanup(ids, vrp_session, vrp_session2):
    test_ensure_clean_workspace(ids, vrp_session, vrp_session2)
