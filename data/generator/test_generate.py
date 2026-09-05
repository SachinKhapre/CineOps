"""Self-check: incident slot detection matches ground truth, and only fires
on the incident day/segment/hour combination."""
from generate import is_incident_slot, NUM_DAYS

incident_day = NUM_DAYS - 1

assert is_incident_slot(incident_day, "Android", "Maharashtra", "1080p", 20)
assert is_incident_slot(incident_day, "Android", "Maharashtra", "4K", 19)
assert not is_incident_slot(incident_day, "Android", "Maharashtra", "1080p", 18)  # before window
assert not is_incident_slot(incident_day, "Android", "Maharashtra", "1080p", 22)  # window end exclusive
assert not is_incident_slot(incident_day, "iOS", "Maharashtra", "1080p", 20)  # wrong device
assert not is_incident_slot(incident_day, "Android", "Karnataka", "1080p", 20)  # wrong region
assert not is_incident_slot(incident_day, "Android", "Maharashtra", "720p", 20)  # wrong quality
assert not is_incident_slot(0, "Android", "Maharashtra", "1080p", 20)  # wrong day

print("ok")
