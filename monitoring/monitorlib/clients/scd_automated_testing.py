import uuid
from datetime import datetime
from typing import Tuple
import requests
from monitoring.monitorlib import fetch

from monitoring.monitorlib.clients.scd import OperationError
from monitoring.monitorlib.infrastructure import DSSTestSession
from monitoring.monitorlib.scd_automated_testing.scd_injection_api import InjectFlightRequest, InjectFlightResponse, \
    SCOPE_SCD_QUALIFIER_INJECT, InjectFlightResult, DeleteFlightResponse, DeleteFlightResult
from monitoring.monitorlib.typing import ImplicitDict


class QueryError(OperationError):
    """An error encountered when interacting with a DSS or a USS"""
    def __init__(self, msg, query: fetch.Query):
        super(OperationError, self).__init__(msg)
        self.query = query


def create_flight(utm_client: DSSTestSession, uss_base_url: str, flight_request: InjectFlightRequest) -> Tuple[str, InjectFlightResponse, fetch.Query]:
    flight_id = str(uuid.uuid4())
    url = '{}/v1/flights/{}'.format(uss_base_url, flight_id)
    print("[SCD] PUT {}".format(url))

    initiated_at = datetime.utcnow()
    resp = utm_client.put(url, json=flight_request, scope=SCOPE_SCD_QUALIFIER_INJECT)
    if resp.status_code != 200:
        raise QueryError('Unexpected response code for createFlight {}. Response: {}'.format(resp.status_code, resp.content.decode('utf-8')), fetch.describe_query(resp, initiated_at))
    return flight_id, ImplicitDict.parse(resp.json(), InjectFlightResponse), fetch.describe_query(resp, initiated_at)


def delete_flight(utm_client: DSSTestSession, uss_base_url: str, flight_id: str) -> Tuple[DeleteFlightResponse, fetch.Query]:
    url = '{}/v1/flights/{}'.format(uss_base_url, flight_id)
    print("[SCD] DELETE {}".format(url))

    initiated_at = datetime.utcnow()
    resp = utm_client.delete(url, scope=SCOPE_SCD_QUALIFIER_INJECT)
    if resp.status_code != 200:
        raise QueryError('Unexpected response code for deleteFlight {}. Response: {}'.format(resp.status_code, resp.content.decode('utf-8')), fetch.describe_query(resp, initiated_at))

    return ImplicitDict.parse(resp.json(), DeleteFlightResponse), fetch.describe_query(resp, initiated_at)


