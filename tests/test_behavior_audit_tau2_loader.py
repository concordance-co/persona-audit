from __future__ import annotations

import json

from backend.api.tau2_loader import load_tau2_traces, payload_to_trace


def test_payload_to_trace_normalizes_tau2_messages() -> None:
    trace = payload_to_trace(
        {
            "domain": "airline",
            "task_id": "change_flight",
            "user_id": "traveler_123",
            "reward": 1.0,
            "messages": [
                {"role": "user", "content": "Please change my flight."},
                {"role": "agent", "content": "I can help after confirming the itinerary."},
            ],
        },
        index=3,
    )

    assert trace.trace_id == "airline_change_flight_3"
    assert trace.user_id == "traveler_123"
    assert trace.outcome == "pass"
    assert [turn.role for turn in trace.turns] == ["user", "assistant"]
    assert trace.labels["is_high_stakes_candidate"] is False


def test_payload_to_trace_preserves_tau2_reward_labels() -> None:
    trace = payload_to_trace(
        {
            "domain": "airline",
            "task_id": "change_flight",
            "reward_info": {
                "reward": 0.0,
                "db_check": {"db_match": False, "db_reward": 0.0},
                "reward_breakdown": {"DB": 0.0, "COMMUNICATE": 1.0},
                "action_checks": [
                    {
                        "action": {
                            "action_id": "change_flight_0",
                            "name": "update_reservation_flights",
                            "arguments": {"reservation_id": "ABC123"},
                        },
                        "action_match": False,
                        "action_reward": 0.0,
                    }
                ],
                "nl_assertions": [
                    {
                        "nl_assertion": "Agent explains the flight could not be changed.",
                        "met": True,
                        "justification": "The assistant explained the restriction.",
                    }
                ],
            },
            "messages": [
                {"role": "agent", "content": "I can help."},
                {
                    "role": "agent",
                    "content": None,
                    "tool_calls": [
                        {
                            "name": "update_reservation_flights",
                            "arguments": {"reservation_id": "ABC123"},
                        }
                    ],
                    "turn_idx": 2,
                },
            ],
        },
        index=7,
    )

    tau2_eval = trace.metadata["tau2_eval"]
    assert tau2_eval["available"] is True
    assert tau2_eval["db_check"]["db_match"] is False
    assert tau2_eval["actions"][0]["met"] is False
    assert tau2_eval["nl_assertions"][0]["met"] is True
    assert tau2_eval["turn_labels"][0]["kind"] == "action_mismatch"
    assert trace.metadata["final_action"] == "update_reservation_flights"
    assert trace.metadata["reward_breakdown"] == {"DB": 0.0, "COMMUNICATE": 1.0}


def test_payload_to_trace_distributes_multi_tool_labels_to_normalized_turns() -> None:
    trace = payload_to_trace(
        {
            "domain": "airline",
            "task_id": "flight_status",
            "reward_info": {
                "reward": 1.0,
                "action_checks": [
                    {
                        "action": {
                            "action_id": "flight_status_0",
                            "name": "get_flight_status",
                            "arguments": {"flight_number": "HAT228"},
                        },
                        "action_match": True,
                        "action_reward": 1.0,
                    }
                ],
            },
            "messages": [
                {"role": "user", "content": "Check these flights."},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"name": "get_flight_status", "arguments": {"flight_number": "HAT228"}},
                        {"name": "get_flight_status", "arguments": {"flight_number": "HAT202"}},
                    ],
                    "turn_idx": 1,
                },
            ],
        },
        index=8,
    )

    labels = trace.metadata["tau2_eval"]["turn_labels"]
    assert [turn.index for turn in trace.turns] == [0, 1, 2]
    assert [turn.tool_name for turn in trace.turns[1:]] == ["get_flight_status", "get_flight_status"]
    assert [label["turn_index"] for label in labels] == [1, 2]
    assert [label["kind"] for label in labels] == ["action_match", "action_unchecked"]


def test_load_tau2_traces_accepts_result_collections(tmp_path) -> None:
    path = tmp_path / "results.json"
    path.write_text(
        json.dumps(
            {
                "simulations": [
                    {
                        "domain": "banking",
                        "task_id": "wire",
                        "reward": 0.0,
                        "trajectory": [
                            {"role": "customer", "content": "Send the wire."},
                            {"role": "agent", "content": "Done."},
                        ],
                    }
                ],
                "tasks": [
                    {
                        "id": "wire",
                        "description": "Send a wire after verification.",
                        "user_scenario": {
                            "instructions": {
                                "reason_for_call": "Customer wants to send a wire.",
                                "task_instructions": "Verify identity before sending funds.",
                            }
                        },
                        "evaluation_criteria": {
                            "actions": [{"name": "send_wire"}],
                            "reward_basis": ["Correct account state"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    traces = load_tau2_traces(str(path))

    assert len(traces) == 1
    assert traces[0].domain == "banking"
    assert traces[0].outcome == "fail"
    assert traces[0].labels["is_high_stakes_candidate"] is True
    assert traces[0].metadata["task"]["reason_for_call"] == "Customer wants to send a wire."
    assert traces[0].metadata["task"]["expected_actions"] == ["send_wire"]
