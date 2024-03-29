"""Basic strategic conflict detection Subscription tests:

  - make sure Subscription doesn't exist by ID
  - create the Subscription with a 60 minute expiry
  - get by ID
  - mutate
  - delete
  - make sure Subscription can't be found by ID
"""

import datetime
from typing import Dict
from typing import Literal

from monitoring.monitorlib import scd
from monitoring.monitorlib.testing import assert_datetimes_are_equal
from monitoring.prober.infrastructure import for_api_versions, register_resource_type
from monitoring.monitorlib.typing import ImplicitDict, StringBasedDateTime
from monitoring.monitorlib.infrastructure import DSSTestSession


SCOPE_VRP = 'utm.vertiport_management'

SUB_TYPE = register_resource_type(220, 'Subscription')


class Time(ImplicitDict):
    ''' A class to hold Time details '''
    value: StringBasedDateTime
    format:Literal['RFC3339']

def make_time(t: datetime) -> Time:
    return Time(value=t.isoformat() + 'Z', format='RFC3339')


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


def _check_sub1(data, sub_id):
  assert data['subscription']['id'] == sub_id
  assert (('notification_index' not in data['subscription']) or
          (data['subscription']['notification_index'] == 0))
  assert data['subscription']['uss_base_url'] == 'https://example.com/foo'
  assert data['subscription']['time_start']['format'] == scd.TIME_FORMAT_CODE
  assert data['subscription']['time_end']['format'] == scd.TIME_FORMAT_CODE
  assert (('notify_for_constraints' not in data['subscription']) or
          (data['subscription']['notify_for_constraints'] == False))
  assert (('implicit_subscription' not in data['subscription']) or
            (data['subscription']['implicit_subscription'] == False))

  assert data['subscription']['notify_for_operational_intents'] == True
  assert (('dependent_operational_intents' not in data['subscription'])
          or len(data['subscription']['dependent_operational_intents']) == 0)


def test_ensure_clean_workspace(ids, vrp_session):
    delete_subscription_if_exists(ids(SUB_TYPE), vrp_session)


def test_sub_does_not_exist_get(ids, scd_api, vrp_session, scope=SCOPE_VRP):
  if vrp_session is None:
    return
  resp = vrp_session.get('/subscriptions/{}'.format(ids(SUB_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 404, resp.content


def test_create_sub(ids, vrp_session, scope=SCOPE_VRP):
  if vrp_session is None:
    return

  req1 = _make_sub1_req()
  resp = vrp_session.put('/subscriptions/{}'.format(ids(SUB_TYPE)), json=req1, scope=SCOPE_VRP)

  assert resp.status_code == 200, resp.content

  data = resp.json()
  assert_datetimes_are_equal(data['subscription']['time_start']['value'], req1['vertiport_reservation']['time_start']['value'])
  assert_datetimes_are_equal(data['subscription']['time_end']['value'], req1['vertiport_reservation']['time_end']['value'])
  _check_sub1(data, ids(SUB_TYPE))


def test_get_sub_by_id(ids, vrp_session, scope=SCOPE_VRP):
  if vrp_session is None:
    return
  resp = vrp_session.get('/subscriptions/{}'.format(ids(SUB_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  data = resp.json()
  _check_sub1(data, ids(SUB_TYPE))


def test_mutate_zone_sub(ids, vrp_session, scope=SCOPE_VRP):
  if vrp_session is None:
    return

  # GET current sub1 before mutation
  resp = vrp_session.get('/subscriptions/{}'.format(ids(SUB_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  existing_sub = resp.json().get('subscription', None)
  assert existing_sub is not None

  req1 = _make_sub1_req()
  req1['vertiport_reservation']['vertiport_zone'] = 1

  resp = vrp_session.put('/subscriptions/{}/{}'.format(ids(SUB_TYPE), existing_sub['version']), json=req1, scope=SCOPE_VRP)

  assert resp.status_code == 200, resp.content

  data = resp.json()
  assert_datetimes_are_equal(data['subscription']['time_start']['value'], req1['vertiport_reservation']['time_start']['value'])
  assert_datetimes_are_equal(data['subscription']['time_end']['value'], req1['vertiport_reservation']['time_end']['value'])


def test_mutate_constraints_sub(ids, vrp_session, scope=SCOPE_VRP):
  if vrp_session is None:
    return

  # GET current sub1 before mutation
  resp = vrp_session.get('/subscriptions/{}'.format(ids(SUB_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  existing_sub = resp.json().get('subscription', None)
  assert existing_sub is not None

  req1 = _make_sub1_req()
  req1['notify_for_constraints'] = True

  resp = vrp_session.put('/subscriptions/{}/{}'.format(ids(SUB_TYPE), existing_sub['version']), json=req1, scope=SCOPE_VRP)

  assert resp.status_code == 200, resp.content

  data = resp.json()
  assert_datetimes_are_equal(data['subscription']['time_start']['value'], req1['vertiport_reservation']['time_start']['value'])
  assert_datetimes_are_equal(data['subscription']['time_end']['value'], req1['vertiport_reservation']['time_end']['value'])


def test_delete_sub(ids, vrp_session, scope=SCOPE_VRP):
  if vrp_session is None:
    return
  resp = vrp_session.get('/subscriptions/{}'.format(ids(SUB_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content
  resp = vrp_session.delete('/subscriptions/{}/{}'.format(ids(SUB_TYPE), resp.json()['subscription']['version']), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content


def test_get_deleted_sub_by_id(ids, vrp_session, scope=SCOPE_VRP):
  if vrp_session is None:
    return
  resp = vrp_session.get('/subscriptions/{}'.format(ids(SUB_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 404, resp.content


def test_final_cleanup(ids, vrp_session, scope=SCOPE_VRP):
    test_ensure_clean_workspace(ids, vrp_session)
