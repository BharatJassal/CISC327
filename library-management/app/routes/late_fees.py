from flask import Blueprint, jsonify, request

from app import store

late_fees_bp = Blueprint("late_fees", __name__, url_prefix="/policy/late-fees")

FIELDS = ("fines_enabled", "grace_period_days", "daily_rate", "max_fine")


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate(data):
    """Return an error message, or None if update is valid."""
    if not isinstance(data, dict) or not data:
        return "Send at least one setting"
    for key in data:
        if key not in FIELDS:
            return f"Unknown setting: {key}"
    if "fines_enabled" in data and not isinstance(data["fines_enabled"], bool):
        return "fines_enabled must be true or false"
    if "grace_period_days" in data:
        days = data["grace_period_days"]
        if not isinstance(days, int) or isinstance(days, bool) or days < 0:
            return "grace_period_days must be a whole number of at least 0"
    if "daily_rate" in data:
        rate = data["daily_rate"]
        if not is_number(rate) or rate < 0:
            return "daily_rate must be a number at least 0"
    if "max_fine" in data and data["max_fine"] is not None:
        cap = data["max_fine"]
        if not is_number(cap) or cap < 0:
            return "max_fine must be a number at least 0, or null for no cap"
    return None


@late_fees_bp.route("", methods=["GET"])
def get_late_fees():
    return jsonify(store.late_fee_policy.to_dict())


@late_fees_bp.route("", methods=["PUT"])
def update_late_fees():
    data = request.get_json(silent=True)
    error = validate(data)
    if error:
        return jsonify({"error": error}), 400
    for key in FIELDS:
        if key in data:
            setattr(store.late_fee_policy, key, data[key])
    return jsonify(store.late_fee_policy.to_dict())