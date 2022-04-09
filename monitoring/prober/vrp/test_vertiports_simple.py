"""Basic Vertiport tests:

  - make sure the Vertiport doesn't exist with get or query
  - create the Vertiport with 5 parking places
  - get by ID
  - change
  - delete
  - get the number of used parking places
  - get available times at FATO
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
VERTIPORT_TYPE = register_resource_type(1, 'Vertiport 1')
OP1_TYPE = register_resource_type(213, 'Operational intent 1')
OP2_TYPE = register_resource_type(214, 'Operational intent 2')
CONSTRAINT_TYPE = register_resource_type(2, 'Single constraint')

SCOPE_VRP = 'utm.vertiport_management'

def delete_vertiport_if_exists(id: str, vrp_session: DSSTestSession):
    resp = vrp_session.get('/{}'.format(id), scope=SCOPE_VRP)
    if resp.status_code == 200:
        resp = vrp_session.delete('/{}'.format(id), scope=SCOPE_VRP)
        assert resp.status_code == 200, '{}: {}'.format(resp.url, resp.content)
    elif resp.status_code == 404:
        # As expected.
        pass
    else:
        print(resp.content)
        assert False, resp.content


def test_ensure_clean_workspace(ids, vrp_session):
    delete_vertiport_if_exists(ids(VERTIPORT_TYPE), vrp_session)


class Time(ImplicitDict):
    ''' A class to hold Time details '''
    value: StringBasedDateTime
    format:Literal['RFC3339']


def make_time(t: datetime) -> Time:
    return Time(value=t.isoformat() + 'Z', format='RFC3339')


def _create_vertiport1_request():
    return {
        'number_of_parking_places': 5,
    }


@depends_on(test_ensure_clean_workspace)
def test_create_vertiport(ids, vrp_session):
  id = ids(VERTIPORT_TYPE)
  req = _create_vertiport1_request()

  resp = vrp_session.put('/{}'.format(id), json=req, scope=SCOPE_VRP)
  print(resp.content)
  assert resp.status_code == 200, resp.content

  data = resp.json()
  constraint = data['vertiport']
  assert constraint['id'] == id
  assert constraint['number_of_parking_places'] == 5


@depends_on(test_ensure_clean_workspace)
def test_get_vertiport_by_id(ids, vrp_session):
    id = ids(VERTIPORT_TYPE)
    req = _create_vertiport1_request()

    resp = vrp_session.put('/{}'.format(id), json=req, scope=SCOPE_VRP)
    print(resp.content)
    assert resp.status_code == 200, resp.content

    resp = vrp_session.get('/{}'.format(id), scope=SCOPE_VRP)
    assert resp.status_code == 200, resp.content

    data = resp.json()
    constraint = data['vertiport']
    assert constraint['id'] == id
    assert constraint['number_of_parking_places'] == 5


@depends_on(test_create_vertiport)
def test_delete_vertiport_by_id(ids, vrp_session):
    id = ids(VERTIPORT_TYPE)

    resp = vrp_session.delete('/{}'.format(id), scope=SCOPE_VRP)
    assert resp.status_code == 200, resp.content

    resp = vrp_session.get('/{}'.format(id), scope=SCOPE_VRP)
    assert resp.status_code == 404


@depends_on(test_ensure_clean_workspace)
def test_update_vertiport(ids, vrp_session):
    id = ids(VERTIPORT_TYPE)
    req = _create_vertiport1_request()

    resp = vrp_session.put('/{}'.format(id), json=req, scope=SCOPE_VRP)
    print(resp.content)
    assert resp.status_code == 200, resp.content

    req['number_of_parking_places'] = 10

    resp = vrp_session.put('/{}'.format(id), json=req, scope=SCOPE_VRP)
    assert resp.status_code == 200, resp.content

    resp = vrp_session.get('/{}'.format(id), scope=SCOPE_VRP)
    assert resp.status_code == 200, resp.content

    data = resp.json()
    constraint = data['vertiport']
    assert constraint['id'] == id
    assert constraint['number_of_parking_places'] == 10



def create_op_and_constraints(vrp_operations, vrp_constraints, vrp_session, ids):
    for op, idd in vrp_operations:
        resp = vrp_session.get('/operational_intent_references/{}'.format(idd), scope=SCOPE_VRP)

        if resp.status_code == 200:
            data = resp.json().get('operational_intent_reference', None)
            resp = vrp_session.delete('/operational_intent_references/{}/{}'.format(idd, data['ovn']), scope=SCOPE_VRP)

            assert resp.status_code == 200, resp.content

        resp = vrp_session.put('/operational_intent_references/{}'.format(idd), json=op, scope=SCOPE_VRP)

        assert resp.status_code == 200, resp.content

    for constr, idd in vrp_constraints:
        resp = vrp_session.get('/constraint_references/{}'.format(idd), scope=SCOPE_VRP)

        if resp.status_code == 200:
            data = resp.json().get('constraint_reference', None)
            resp = vrp_session.delete('/constraint_references/{}/{}'.format(idd, data['ovn']), scope=SCOPE_VRP)

            assert resp.status_code == 200, resp.content


        resp = vrp_session.put('/constraint_references/{}'.format(idd), json=constr, scope=SCOPE_VRP)

        assert resp.status_code == 200, resp.content


@depends_on(test_ensure_clean_workspace)
def test_get_number_of_free_parking_places_1(ids, vrp_session):
    id = ids(VERTIPORT_TYPE)
    req = _create_vertiport1_request()

    resp = vrp_session.put('/{}'.format(id), json=req, scope=SCOPE_VRP)

    time_start = datetime.datetime.utcnow()
    time_end = time_start + datetime.timedelta(minutes=60)

    vrp_operations = [(
        {
            'vertiport_reservation':
                {'time_start': make_time(time_start),
                 'time_end': make_time(time_end),
                 'vertiportid': id,
                 'reserved_zone': 1,
                 },
            'old_version': 0,
            'state': 'Accepted',
            'uss_base_url': 'whatever',
            'new_subscription': {
                'uss_base_url': 'whatever2',
                'notify_for_constraints': False
            }
        }, ids(OP1_TYPE)
    )
    ]
    vrp_constraints = [(
        {
            'vertiport_reservation': {
                'time_start': make_time(time_start),
                'time_end': make_time(time_end),
                'vertiportid': id,
                'reserved_zone': 1,
            },
            'old_version': 0,
            'uss_base_url': BASE_URL,
        }, ids(CONSTRAINT_TYPE)
    )
    ]

    create_op_and_constraints(vrp_operations, vrp_constraints, vrp_session, ids)

    resp = vrp_session.post('/number_of_used_parking_places/{}'.format(id), json={
        'time_start': make_time(time_start),
        'time_end': make_time(time_end)
    }, scope=SCOPE_VRP)

    assert resp.status_code == 200, resp.content

    data = resp.json()
    assert data['number_of_used_places'] == 2, data
    assert data['number_of_available_places'] == 3
    assert data['number_of_places'] == 5


@depends_on(test_ensure_clean_workspace)
def test_get_number_of_free_parking_places_2(ids, vrp_session):
    id = ids(VERTIPORT_TYPE)
    req = _create_vertiport1_request()

    resp = vrp_session.put('/{}'.format(id), json=req, scope=SCOPE_VRP)

    time_start = datetime.datetime.utcnow()
    time_end = time_start + datetime.timedelta(minutes=60)

    vrp_operations = [(
        {
            'vertiport_reservation':
                {'time_start': make_time(time_start),
                 'time_end': make_time(time_start + datetime.timedelta(minutes=20)),
                 'vertiportid': id,
                 'reserved_zone': 1,
                 },
            'old_version': 0,
            'state': 'Accepted',
            'uss_base_url': 'whatever',
            'new_subscription': {
                'uss_base_url': 'whatever2',
                'notify_for_constraints': False
            }
        }, ids(OP1_TYPE)
    )
    ]
    vrp_constraints = [(
        {
            'vertiport_reservation': {
                'time_start': make_time(time_start + datetime.timedelta(minutes=30)),
                'time_end': make_time(time_start + datetime.timedelta(minutes=50)),
                'vertiportid': id,
                'reserved_zone': 1,
            },
            'old_version': 0,
            'uss_base_url': BASE_URL,
        }, ids(CONSTRAINT_TYPE)
    )
    ]

    create_op_and_constraints(vrp_operations, vrp_constraints, vrp_session, ids)

    resp = vrp_session.post('/number_of_used_parking_places/{}'.format(id), json={
        'time_start': make_time(time_start),
        'time_end': make_time(time_start + datetime.timedelta(minutes=60))
    }, scope=SCOPE_VRP)

    assert resp.status_code == 200, resp.content

    data = resp.json()
    assert data['number_of_used_places'] == 1, data
    assert data['number_of_available_places'] == 4
    assert data['number_of_places'] == 5


@depends_on(test_ensure_clean_workspace)
def test_get_free_times(ids, vrp_session):
    id = ids(VERTIPORT_TYPE)
    req = _create_vertiport1_request()

    resp = vrp_session.put('/{}'.format(id), json=req, scope=SCOPE_VRP)

    time_start = datetime.datetime.utcnow()
    time_end = time_start + datetime.timedelta(minutes=60)

    vrp_operations = [(
        {
            'vertiport_reservation':
                {'time_start': make_time(time_start + datetime.timedelta(minutes=5)),
                 'time_end': make_time(time_start + datetime.timedelta(minutes=20)),
                 'vertiportid': id,
                 'reserved_zone': 0,
                 },
            'old_version': 0,
            'state': 'Accepted',
            'uss_base_url': 'whatever',
            'new_subscription': {
                'uss_base_url': 'whatever2',
                'notify_for_constraints': False
            }
        }, ids(OP1_TYPE)
    )
    ]
    vrp_constraints = [(
        {
            'vertiport_reservation': {
                'time_start': make_time(time_start + datetime.timedelta(minutes=30)),
                'time_end': make_time(time_start + datetime.timedelta(minutes=50)),
                'vertiportid': id,
                'reserved_zone': 0,
            },
            'old_version': 0,
            'uss_base_url': BASE_URL,
        }, ids(CONSTRAINT_TYPE)
    )
    ]

    create_op_and_constraints(vrp_operations, vrp_constraints, vrp_session, ids)

    resp = vrp_session.post('/fato_available_times/{}'.format(id), json={
        'time_start': make_time(time_start),
        'time_end': make_time(time_start + datetime.timedelta(minutes=60))
    }, scope=SCOPE_VRP)

    assert resp.status_code == 200, resp.content


    print(resp.content)

    data = resp.json()
    print(data)
    assert len(data['time_period']) == 3

    assert_datetimes_are_equal(make_time(time_start)['value'], data['time_period'][0]['from']['value'])
    assert_datetimes_are_equal(make_time(time_start + datetime.timedelta(minutes=5))['value'], data['time_period'][0]['to']['value'])


    assert_datetimes_are_equal(make_time(time_start + datetime.timedelta(minutes=20))['value'], data['time_period'][1]['from']['value'])
    assert_datetimes_are_equal(make_time(time_start + datetime.timedelta(minutes=30))['value'], data['time_period'][1]['to']['value'])


    assert_datetimes_are_equal(make_time(time_start + datetime.timedelta(minutes=50))['value'], data['time_period'][2]['from']['value'])
    assert_datetimes_are_equal(make_time(time_start + datetime.timedelta(minutes=60))['value'], data['time_period'][2]['to']['value'])


@depends_on(test_ensure_clean_workspace)
def test_get_free_times_2(ids, vrp_session):
    id = ids(VERTIPORT_TYPE)
    req = _create_vertiport1_request()

    resp = vrp_session.put('/{}'.format(id), json=req, scope=SCOPE_VRP)

    time_start = datetime.datetime.utcnow()
    time_end = time_start + datetime.timedelta(minutes=60)

    vrp_operations = [(
        {
            'vertiport_reservation':
                {'time_start': make_time(time_start + datetime.timedelta(minutes=-5)),
                 'time_end': make_time(time_start + datetime.timedelta(minutes=20)),
                 'vertiportid': id,
                 'reserved_zone': 0,
                 },
            'old_version': 0,
            'state': 'Accepted',
            'uss_base_url': 'whatever',
            'new_subscription': {
                'uss_base_url': 'whatever2',
                'notify_for_constraints': False
            }
        }, ids(OP1_TYPE)
    )
    ]
    vrp_constraints = [(
        {
            'vertiport_reservation': {
                'time_start': make_time(time_start + datetime.timedelta(minutes=30)),
                'time_end': make_time(time_start + datetime.timedelta(minutes=70)),
                'vertiportid': id,
                'reserved_zone': 0,
            },
            'old_version': 0,
            'uss_base_url': BASE_URL,
        }, ids(CONSTRAINT_TYPE)
    )
    ]

    create_op_and_constraints(vrp_operations, vrp_constraints, vrp_session, ids)

    resp = vrp_session.post('/fato_available_times/{}'.format(id), json={
        'time_start': make_time(time_start),
        'time_end': make_time(time_start + datetime.timedelta(minutes=60))
    }, scope=SCOPE_VRP)

    assert resp.status_code == 200, resp.content


    print(resp.content)

    data = resp.json()
    print(data)
    assert len(data['time_period']) == 1

    assert_datetimes_are_equal(make_time(time_start + datetime.timedelta(minutes=20))['value'], data['time_period'][0]['from']['value'])
    assert_datetimes_are_equal(make_time(time_start + datetime.timedelta(minutes=30))['value'], data['time_period'][0]['to']['value'])

