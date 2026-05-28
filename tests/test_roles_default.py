from __future__ import annotations

from server.roles import get_assignment


def test_default_nine_subject_role_schedule() -> None:
    subject_count = 9
    participants = [f"P{i:02d}" for i in range(1, subject_count + 1)]

    m1 = [get_assignment(1, pid, 1, subject_count=subject_count) for pid in participants]
    m2 = [get_assignment(1, pid, 2, subject_count=subject_count) for pid in participants]
    m3 = [get_assignment(1, pid, 3, subject_count=subject_count) for pid in participants]
    m4 = [get_assignment(1, pid, 4, subject_count=subject_count) for pid in participants]

    assert sum(1 for r in m1 if r.role_tier == "uninformed" and r.endowment_tokens == 100.0) == 9
    assert sum(1 for r in m2 if r.role_tier == "informed" and r.endowment_tokens == 100.0) == 3
    assert sum(1 for r in m2 if r.role_tier == "uninformed" and r.endowment_tokens == 100.0) == 6
    assert sum(1 for r in m3 if r.role_tier == "uninformed" and r.endowment_tokens == 400.0) == 2
    assert sum(1 for r in m3 if r.role_tier == "uninformed" and r.endowment_tokens == 100.0) == 7
    assert sum(1 for r in m4 if r.role_tier == "informed" and r.endowment_tokens == 400.0) == 2
    assert sum(1 for r in m4 if r.role_tier == "informed" and r.endowment_tokens == 100.0) == 1
    assert sum(1 for r in m4 if r.role_tier == "uninformed" and r.endowment_tokens == 100.0) == 6
