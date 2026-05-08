from actions.actions import (
    ActionCollectTripPreferences,
    ActionPackageHandoverContext,
    ActionRecommendHotels,
    ActionTwoStageClarification,
    ClimatiqClient,
    RecommendationEngine,
)


class DummyDispatcher:
    def __init__(self):
        self.messages = []

    def utter_message(self, **kwargs):
        self.messages.append(kwargs)


class DummyTracker:
    def __init__(self, slots=None, latest_text="latest message"):
        self.slots = slots or {}
        self.latest_message = {"text": latest_text}

    def get_slot(self, key):
        return self.slots.get(key)


def get_slot_value(events, name):
    for event in events:
        if event.get("event") == "slot" and event.get("name") == name:
            return event.get("value")
    return None


def has_followup_action(events, action_name):
    return any(event.get("event") == "followup" and event.get("name") == action_name for event in events)


def test_recommendation_weights_change_with_sustainability_level():
    options = [
        {"id": "cheap_high_carbon", "name": "Cheap Flight", "price": 30, "carbon_kg": 140, "relevance": 0.8},
        {"id": "green_train", "name": "Green Train", "price": 90, "carbon_kg": 20, "relevance": 0.9},
    ]
    high = RecommendationEngine.rank_options(options, "high", 200, "transport")
    assert high[0]["id"] == "green_train"


def test_climatiq_missing_key_uses_mock_fallback(monkeypatch):
    monkeypatch.delenv("CLIMATIQ_API_KEY", raising=False)
    client = ClimatiqClient(api_key=None)
    result = client.estimate_transport("train", origin="Berlin", destination="Amsterdam")
    assert result["source"] == "mock_emission_factor"
    assert result["carbon_kg"] > 0
    assert "missing" in result["fallback_reason"]


def test_handover_context_contains_required_fields():
    dispatcher = DummyDispatcher()
    tracker = DummyTracker(
        slots={
            "destination": "Amsterdam",
            "origin": "Berlin",
            "travel_date": "12 June",
            "return_date": "15 June",
            "budget": "700",
            "sustainability_level": "high",
            "transport_mode": "train",
            "recommended_options": {"transport": []},
        },
        latest_text="I need a human advisor",
    )
    events = ActionPackageHandoverContext().run(dispatcher, tracker, {})
    summary = get_slot_value(events, "conversation_summary")
    assert summary["destination"] == "Amsterdam"
    assert summary["origin"] == "Berlin"
    assert summary["latest_user_message"] == "I need a human advisor"
    assert get_slot_value(events, "handover_required") is True


def test_collect_trip_preferences_requests_next_missing_slot():
    dispatcher = DummyDispatcher()
    tracker = DummyTracker(slots={"destination": "Amsterdam"})
    events = ActionCollectTripPreferences().run(dispatcher, tracker, {})
    assert events == []
    assert dispatcher.messages[0]["text"] == "Where will you travel from?"


def test_collect_trip_preferences_confirms_when_complete():
    dispatcher = DummyDispatcher()
    tracker = DummyTracker(
        slots={
            "destination": "Amsterdam",
            "origin": "Berlin",
            "travel_date": "12 June",
            "return_date": "15 June",
            "budget": "700",
            "sustainability_level": "high",
        }
    )
    events = ActionCollectTripPreferences().run(dispatcher, tracker, {})
    assert events == []
    assert dispatcher.messages[0]["text"] == "Thank you. I have enough information to prepare sustainable recommendations."
    assert "Trip summary: Berlin to Amsterdam" in dispatcher.messages[1]["text"]


def test_two_stage_clarification_first_attempt_asks_options():
    dispatcher = DummyDispatcher()
    tracker = DummyTracker(slots={"clarification_attempts": 0})
    events = ActionTwoStageClarification().run(dispatcher, tracker, {})
    assert dispatcher.messages
    assert dispatcher.messages[0]["buttons"]
    assert get_slot_value(events, "clarification_attempts") == 1


def test_two_stage_clarification_second_attempt_triggers_handover():
    dispatcher = DummyDispatcher()
    tracker = DummyTracker(slots={"clarification_attempts": 1})
    events = ActionTwoStageClarification().run(dispatcher, tracker, {})
    assert has_followup_action(events, "action_package_handover_context")
    assert get_slot_value(events, "handover_required") is True


def test_recommend_hotels_returns_cards():
    dispatcher = DummyDispatcher()
    tracker = DummyTracker(
        slots={
            "destination": "Amsterdam",
            "budget": "700",
            "sustainability_level": "high",
            "accommodation_type": "eco hotel",
        }
    )
    events = ActionRecommendHotels().run(dispatcher, tracker, {})
    assert dispatcher.messages
    assert dispatcher.messages[0]["json_message"]["cards"]
    assert get_slot_value(events, "selected_option") is not None
