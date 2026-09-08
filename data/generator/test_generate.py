"""Self-check: incident injection fires only on the intended slots, and each
incident leaves the other one's signal alone."""
from generate import (
    BASE_BUFFER_PROB,
    BASE_COMPLETION_PROB,
    INCIDENT_A_BUFFER_PROB,
    INCIDENT_C_COMPLETION_PROB,
    INCIDENT_C_CONTENT_ID,
    NUM_DAYS,
    is_incident_a_slot,
    is_incident_c_slot,
    session_probabilities,
)

incident_day = NUM_DAYS - 1
OTHER_CONTENT = "c0001"

# --- Incident A: playback degradation, narrow to device+region+quality+hours ---
assert is_incident_a_slot(incident_day, "Android", "Maharashtra", "1080p", 20)
assert is_incident_a_slot(incident_day, "Android", "Maharashtra", "4K", 19)
assert not is_incident_a_slot(incident_day, "Android", "Maharashtra", "1080p", 18)  # before window
assert not is_incident_a_slot(incident_day, "Android", "Maharashtra", "1080p", 22)  # window end exclusive
assert not is_incident_a_slot(incident_day, "iOS", "Maharashtra", "1080p", 20)  # wrong device
assert not is_incident_a_slot(incident_day, "Android", "Karnataka", "1080p", 20)  # wrong region
assert not is_incident_a_slot(incident_day, "Android", "Maharashtra", "720p", 20)  # wrong quality
assert not is_incident_a_slot(0, "Android", "Maharashtra", "1080p", 20)  # wrong day

# --- Incident C: one title, any device/region/quality/hour ---
assert is_incident_c_slot(incident_day, INCIDENT_C_CONTENT_ID)
assert not is_incident_c_slot(incident_day, OTHER_CONTENT)  # wrong title
assert not is_incident_c_slot(0, INCIDENT_C_CONTENT_ID)  # wrong day

# --- only the selected incident is active ---
a_slot = ("a", incident_day, "Android", "Maharashtra", "1080p", 20, OTHER_CONTENT)
buffer_prob, completion_prob, _ = session_probabilities(*a_slot)
assert (buffer_prob, completion_prob) == (INCIDENT_A_BUFFER_PROB, 0.45)

# the same slot with incident C selected must be untouched
buffer_prob, completion_prob, _ = session_probabilities("c", *a_slot[1:])
assert (buffer_prob, completion_prob) == (BASE_BUFFER_PROB, BASE_COMPLETION_PROB)

# Incident C degrades completion and skips but NOT buffering -- that normal
# buffer rate is what should stop the agent blaming infrastructure.
c_slot = ("c", incident_day, "iOS", "England", "720p", 9, INCIDENT_C_CONTENT_ID)
buffer_prob, completion_prob, skip_share = session_probabilities(*c_slot)
assert buffer_prob == BASE_BUFFER_PROB, "incident C must leave playback normal"
assert completion_prob == INCIDENT_C_COMPLETION_PROB
assert skip_share < 0.5  # more non-completions, so a lower share still lifts skip rate

# and with incident A selected, that title is ordinary
assert session_probabilities("a", *c_slot[1:]) == (BASE_BUFFER_PROB, BASE_COMPLETION_PROB, 0.5)

print("ok")
