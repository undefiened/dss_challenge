"""Basic Constraint tests:

  - make sure the Constraint doesn't exist with get by ID
  - create the Constraint with a 60 minute length
  - get by ID
  - mutate
  - delete
  - make sure Constraints can't be found by ID
"""

import datetime
from typing import Literal

from monitoring.monitorlib.infrastructure import default_scope
from monitoring.monitorlib import scd
from monitoring.monitorlib.scd import SCOPE_SC, SCOPE_CI, SCOPE_CM, SCOPE_CP, SCOPE_CM_SA, SCOPE_AA
from monitoring.monitorlib.testing import assert_datetimes_are_equal
from monitoring.monitorlib.typing import ImplicitDict, StringBasedDateTime
from monitoring.prober.infrastructure import depends_on, for_api_versions, register_resource_type
from monitoring.prober.scd import actions
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


# Constraint shouldn't exist by ID
# Preconditions: None
# Mutations: None
def test_constraint_does_not_exist_get(ids, vrp_session):
  id = ids(CONSTRAINT_TYPE)
  resp = vrp_session.get('/constraint_references/{}'.format(id), scope=SCOPE_VRP)
  assert resp.status_code == 404, resp.content


@depends_on(test_ensure_clean_workspace)
def test_create_constraint(ids, vrp_session):
  id = ids(CONSTRAINT_TYPE)
  req = _make_c1_request()

  resp = vrp_session.put('/constraint_references/{}'.format(id), json=req, scope=SCOPE_VRP)
  print(resp.content)
  assert resp.status_code == 200, resp.content

  data = resp.json()
  constraint = data['constraint_reference']
  assert constraint['id'] == id
  assert constraint['uss_base_url'] == BASE_URL
  assert constraint['uss_availability'] == 'Unknown'
  assert_datetimes_are_equal(constraint['time_start']['value'], req['vertiport_reservation']['time_start']['value'])
  assert_datetimes_are_equal(constraint['time_end']['value'], req['vertiport_reservation']['time_end']['value'])
  assert constraint['version'] == 1


@depends_on(test_create_constraint)
def test_get_constraint_by_id(ids, vrp_session):
  id = ids(CONSTRAINT_TYPE)

  auths = (SCOPE_CM, SCOPE_CP)

  resp = vrp_session.get('/constraint_references/{}'.format(id), scope=SCOPE_VRP)
  assert resp.status_code == 200, resp.content

  data = resp.json()
  constraint = data['constraint_reference']
  assert constraint['id'] == id
  assert constraint['uss_base_url'] == BASE_URL
  assert constraint['uss_availability'] == 'Unknown'
  assert constraint['version'] == 1


@depends_on(test_create_constraint)
def test_mutate_constraint(ids, vrp_session):
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
    'uss_base_url': 'https://example.com/uss2'
  }

  ovn = existing_constraint["ovn"]
  resp = vrp_session.put('/constraint_references/{}/{}'.format(id, ovn), json=req, scope=SCOPE_VRP)
  assert resp.status_code == 200, "ovn:{}\nresponse: {}".format(ovn, resp.content)

  data = resp.json()
  constraint = data['constraint_reference']
  assert constraint['id'] == id
  assert constraint['uss_base_url'] == 'https://example.com/uss2'
  assert constraint['uss_availability'] == 'Unknown'
  assert constraint['version'] == 2


@depends_on(test_mutate_constraint)
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


@depends_on(test_delete_constraint)
def test_get_deleted_constraint_by_id(ids, vrp_session):
  resp = vrp_session.get('/constraint_references/{}'.format(ids(CONSTRAINT_TYPE)), scope=SCOPE_VRP)
  assert resp.status_code == 404, resp.content


def test_final_cleanup(ids, vrp_session):
    test_ensure_clean_workspace(ids, vrp_session)