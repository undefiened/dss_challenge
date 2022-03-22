import typing
from typing import Dict, Optional

from monitoring.monitorlib.clients.scd_automated_testing import QueryError
from monitoring.monitorlib.scd_automated_testing.scd_injection_api import InjectFlightResponse
from monitoring.uss_qualifier.common_data_definitions import Severity
from monitoring.uss_qualifier.scd.configuration import SCDQualifierTestConfiguration
from monitoring.uss_qualifier.scd.data_interfaces import AutomatedTest, TestStep, FlightInjectionAttempt
from monitoring.uss_qualifier.scd.executor.errors import TestRunnerError
from monitoring.uss_qualifier.scd.executor.report_recorder import ReportRecorder
from monitoring.uss_qualifier.scd.executor.target import TestTarget
from monitoring.uss_qualifier.scd.executor.test_steps import inject_flight, delete_flight
from monitoring.uss_qualifier.scd.reports import Report, Issue, AutomatedTestContext, TestStepReference, TestPhase


# TODO: Replace print by logging
class TestRunner:
    """A class to run automated test steps for a specific combination of targets per uss role"""

    def __init__(self, context: AutomatedTestContext, automated_test: AutomatedTest, targets: Dict[str, TestTarget], dss_target: Optional[TestTarget], report: Report):
        self.context = context
        self.automated_test = automated_test
        self.targets = targets
        self.dss_target = dss_target
        self.report_recorder = ReportRecorder(report, self.context)


    def get_scd_configuration(self) -> SCDQualifierTestConfiguration:
        return SCDQualifierTestConfiguration(injection_targets=list(map(lambda t: t.config, self.targets.values())))


    def run_automated_test(self):
        for i, step in enumerate(self.automated_test.steps):
            print('[SCD]   Running step {}: {}'.format(i, step.name))
            self.execute_step(step, i)


    def teardown(self):
        """Delete resources created by this test runner."""
        print("[SCD]   Teardown {}".format(self.automated_test.name))

        cleanup_test_step = 0
        for role, target in self.targets.items():
            flight_names = target.managed_flights()
            for flight_name in flight_names:
                print("[SCD]    - Deleting {} flights for target {}.".format(len(flight_names), target.name))

                step_ref = TestStepReference(
                    name="Clean up flight {} in {}".format(flight_name, target.name),
                    index=cleanup_test_step,
                    phase=TestPhase.Cleanup
                )

                try:
                    resp, query = target.delete_flight(flight_name)
                    self.report_recorder.capture_interaction(step_ref, query, 'Remove flight during test cleanup')
                except QueryError as e:
                    interaction_id = self.report_recorder.capture_interaction(step_ref, e.query, 'Remove flight during test cleanup')
                    self.report_recorder.capture_deletion_unknown_issue(
                                    interaction_id=interaction_id,
                                    summary="Deletion request for flight {} was unsuccessful".format(flight_name),
                                    details="Deletion attempt failed with status {}.".format(e.query.status_code),
                                    flight_name=flight_name,
                                    target_name=target.name,
                                    uss_role=role
                            )
                    print("[SCD] Error: Unable to delete flight {} during teardown".format(flight_name))
                cleanup_test_step = cleanup_test_step + 1

    def execute_step(self, step: TestStep, step_index: int):
        target = self.get_target(step)
        if target is None:
            self.print_targets_state()
            raise RuntimeError("[SCD] Error: Unable to identify the target managing flight {}".format(
                step.inject_flight.name if 'inject_flight' in step else step.delete_flight.flight_name
            ))

        step_ref = TestStepReference(
            name=step.name,
            index=step_index,
            phase=TestPhase.Test
        )

        if 'inject_flight' in step:
            inject_flight.execute(self, step, step_ref, target)
        elif 'delete_flight' in step:
            delete_flight.execute(self, step, step_ref, target)
        else:
            raise RuntimeError("[SCD] Error: Unable to identify the action to execute for step {}".format(step.name))

        print("[SCD]     Step {} COMPLETED".format(step.name))

    def get_managing_target(self, flight_name: str) -> typing.Optional[TestTarget]:
        """Returns the managing target which created a flight"""
        for role, target in self.targets.items():
            if target.is_managing_flight(flight_name):
                return target
        return None

    def get_target(self, step: TestStep) -> typing.Optional[TestTarget]:
        """Returns the target which should be called in the TestStep"""
        if 'inject_flight' in step:
            return self.targets[step.inject_flight.injection_target.uss_role]
        elif 'delete_flight' in step:
            return self.get_managing_target(step.delete_flight.flight_name)
        else:
            raise NotImplementedError("Unsupported step. A Test Step shall contain either a inject_flight or a delete_flight object.")

    def get_target_role(self, target_name):
        results = list(filter(lambda x: x[1].name == target_name, self.targets.items()))
        return results[0] if len(results) > 0 else None

    def evaluate_inject_flight_response(self, interaction_id: str, target: TestTarget, attempt: FlightInjectionAttempt, resp: InjectFlightResponse) -> typing.Optional[Issue]:
        if resp.result not in attempt.known_responses.acceptable_results:
            print("[SCD]     Result: ERROR. Received {}, expected one of {}. Reason: {}".format(
                resp.result,
                attempt.known_responses.acceptable_results,
                resp.get('notes', None))
            )
            known_issue = attempt.known_responses.incorrect_result_details.get(resp.result, None)
            if known_issue:
                issue = self.report_recorder.capture_injection_issue(interaction_id=interaction_id, target_name=target.name, attempt=attempt, known_issue=known_issue)
                if known_issue.severity != Severity.Low:
                    raise TestRunnerError("Failed attempt to inject flight {}: {}".format(attempt.name, known_issue.summary), issue)
            else:
                issue = self.report_recorder.capture_injection_unknown_issue(
                    interaction_id=interaction_id,
                    summary="Injection request was unsuccessful",
                    details="Injection attempt failed with unknown response {}".format(resp.result),
                    target_name=target.name,
                    attempt=attempt
                )
                raise TestRunnerError("Unsuccessful attempt to inject flight {}".format(attempt.name), issue)
        return None

    def print_targets_state(self):
        print("[SCD] Targets States:")
        for name, target in self.targets.items():
            print(f"[SCD]   - {name}: {target.created_flight_ids}")
