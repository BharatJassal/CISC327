from flask import Blueprint, jsonify, request

from app import store

policy_bp = Blueprint("policy", __name__, url_prefix="/policy")


@policy_bp.route("", methods=["GET"])
def get_policy():
    return jsonify(store.policy.to_dict())


@policy_bp.route("", methods=["PUT"])
def update_policy():
    data = request.get_json() or {}
    value = data.get("max_loans_per_member")
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        return jsonify({"error": "max_loans_per_member must be a whole number of at least 1"}), 400
    store.policy.max_loans_per_member = value
    return jsonify(store.policy.to_dict())