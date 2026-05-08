"""Custom actions for the Eco Travel Advisor Rasa assistant.

The file is intentionally written in a beginner friendly style. It separates API
clients, recommendation logic, and Rasa action classes so that students can test
and extend each part independently.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Text

import requests
from dotenv import load_dotenv
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import FollowupAction, SlotSet

load_dotenv()
logger = logging.getLogger(__name__)

MOCK_DATA_DIR = Path(__file__).resolve().parent / "mock_data"


def load_mock_json(filename: str) -> List[Dict[str, Any]]:
    """Load local JSON mock data from actions/mock_data."""
    path = MOCK_DATA_DIR / filename
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert text such as '700 euros' to a float where possible."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    digits = "".join(ch for ch in str(value) if ch.isdigit() or ch == ".")
    try:
        return float(digits) if digits else default
    except ValueError:
        return default


def normalise_text(value: Optional[Any]) -> str:
    return str(value or "").strip().lower()


class CarbonImpactClassifier:
    """Classifies carbon values into simple labels for the UI."""

    @staticmethod
    def classify(carbon_kg: float) -> str:
        if carbon_kg <= 25:
            return "green"
        if carbon_kg <= 100:
            return "amber"
        return "red"


class ClimatiqClient:
    """Minimal Climatiq integration wrapper with robust local fallback.

    This project keeps the real API call small and defensive because the
    assistant must remain functional even when the API key is missing, a timeout
    occurs, or the external response shape changes.
    """

    BASE_URL = "https://api.climatiq.io/estimate"

    ACTIVITY_IDS = {
        "train": "passenger_train-route_type_na-fuel_source_na",
        "bus": "passenger_vehicle-vehicle_type_bus-fuel_source_na",
        "flight": "passenger_flight-route_type_domestic-aircraft_type_na-distance_na-class_na-rf_included",
        "car": "passenger_vehicle-vehicle_type_car-fuel_source_na-engine_size_na",
    }

    MOCK_FACTORS_KG_PER_KM = {
        "train": 0.041,
        "bus": 0.027,
        "flight": 0.255,
        "car": 0.171,
        "walking": 0.0,
        "cycling": 0.0,
    }

    MOCK_DISTANCES_KM = {
        ("berlin", "amsterdam"): 655,
        ("london", "copenhagen"): 955,
        ("vienna", "ljubljana"): 385,
        ("munich", "vienna"): 435,
        ("paris", "barcelona"): 1035,
    }

    def __init__(self, api_key: Optional[str] = None, timeout_seconds: int = 8):
        self.api_key = api_key or os.getenv("CLIMATIQ_API_KEY")
        self.timeout_seconds = timeout_seconds

    def estimate_transport(
        self,
        mode: str,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        distance_km: Optional[float] = None,
        passengers: int = 1,
    ) -> Dict[str, Any]:
        mode_key = normalise_text(mode) or "train"
        distance = distance_km or self.mock_distance_km(origin, destination)

        if mode_key in {"walking", "cycling"}:
            return self.mock_estimate(mode_key, distance, passengers, reason="zero direct emissions mode")

        if not self.api_key:
            return self.mock_estimate(mode_key, distance, passengers, reason="missing CLIMATIQ_API_KEY")

        activity_id = self.ACTIVITY_IDS.get(mode_key)
        if not activity_id:
            return self.mock_estimate(mode_key, distance, passengers, reason="unsupported mode for Climatiq")

        payload = {
            "emission_factor": {
                "activity_id": activity_id,
                "data_version": "^21",
            },
            "parameters": {
                "distance": distance,
                "distance_unit": "km",
            },
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            response = requests.post(self.BASE_URL, json=payload, headers=headers, timeout=self.timeout_seconds)
            if response.status_code in {401, 403, 429}:
                return self.mock_estimate(mode_key, distance, passengers, reason=f"Climatiq status {response.status_code}")
            response.raise_for_status()
            data = response.json()
            co2e = float(data.get("co2e", 0)) * max(passengers, 1)
            if co2e <= 0:
                return self.mock_estimate(mode_key, distance, passengers, reason="invalid Climatiq response")
            return {
                "mode": mode_key,
                "carbon_kg": round(co2e, 2),
                "distance_km": round(distance, 1),
                "source": "climatiq_api",
                "fallback_reason": None,
            }
        except requests.Timeout:
            return self.mock_estimate(mode_key, distance, passengers, reason="Climatiq timeout")
        except requests.RequestException as exc:
            logger.warning("Climatiq request failed: %s", exc)
            return self.mock_estimate(mode_key, distance, passengers, reason="Climatiq request error")
        except (ValueError, TypeError) as exc:
            logger.warning("Climatiq response parsing failed: %s", exc)
            return self.mock_estimate(mode_key, distance, passengers, reason="Climatiq invalid response")

    def mock_distance_km(self, origin: Optional[str], destination: Optional[str]) -> float:
        key = (normalise_text(origin), normalise_text(destination))
        reverse_key = (key[1], key[0])
        return float(self.MOCK_DISTANCES_KM.get(key) or self.MOCK_DISTANCES_KM.get(reverse_key) or 500.0)

    def mock_estimate(self, mode: str, distance_km: float, passengers: int, reason: str) -> Dict[str, Any]:
        factor = self.MOCK_FACTORS_KG_PER_KM.get(mode, self.MOCK_FACTORS_KG_PER_KM["train"])
        carbon_kg = distance_km * factor * max(passengers, 1)
        return {
            "mode": mode,
            "carbon_kg": round(carbon_kg, 2),
            "distance_km": round(distance_km, 1),
            "source": "mock_emission_factor",
            "fallback_reason": reason,
        }


class AmadeusClient:
    """Amadeus sandbox integration wrapper with mock fallback.

    The methods demonstrate correct credential handling and failure behaviour.
    Students can replace the placeholder search logic with richer Amadeus
    endpoints when they receive valid sandbox credentials.
    """

    TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
    HOTEL_SEARCH_URL = "https://test.api.amadeus.com/v3/shopping/hotel-offers"
    FLIGHT_SEARCH_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None, timeout_seconds: int = 8):
        self.client_id = client_id or os.getenv("AMADEUS_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("AMADEUS_CLIENT_SECRET")
        self.timeout_seconds = timeout_seconds
        self._access_token: Optional[str] = None

    def has_credentials(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def get_access_token(self) -> Optional[str]:
        if not self.has_credentials():
            logger.info("Amadeus credentials missing. Using mock travel data.")
            return None
        if self._access_token:
            return self._access_token

        try:
            response = requests.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            token = response.json().get("access_token")
            self._access_token = token
            return token
        except requests.RequestException as exc:
            logger.warning("Amadeus token request failed: %s", exc)
            return None

    def search_hotels(self, destination: Optional[str]) -> List[Dict[str, Any]]:
        token = self.get_access_token()
        if not token:
            return self.mock_hotels(destination)

        # Placeholder for a real Amadeus hotel search. The result is normalised
        # to the same local schema so that the recommendation engine stays stable.
        try:
            response = requests.get(
                self.HOTEL_SEARCH_URL,
                headers={"Authorization": f"Bearer {token}"},
                params={"cityCode": self.city_code(destination), "adults": 1},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            raw_items = response.json().get("data", [])
            if not raw_items:
                return self.mock_hotels(destination)
            return self.normalise_hotels(raw_items, destination)
        except requests.RequestException as exc:
            logger.warning("Amadeus hotel search failed: %s", exc)
            return self.mock_hotels(destination)

    def search_flights(self, origin: Optional[str], destination: Optional[str]) -> List[Dict[str, Any]]:
        token = self.get_access_token()
        if not token:
            return load_mock_json("transport_options.json")

        try:
            response = requests.get(
                self.FLIGHT_SEARCH_URL,
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "originLocationCode": self.city_code(origin),
                    "destinationLocationCode": self.city_code(destination),
                    "departureDate": "2026-06-12",
                    "adults": 1,
                    "max": 3,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            if not response.json().get("data"):
                return load_mock_json("transport_options.json")
            return load_mock_json("transport_options.json")
        except requests.RequestException as exc:
            logger.warning("Amadeus flight search failed: %s", exc)
            return load_mock_json("transport_options.json")

    def mock_hotels(self, destination: Optional[str]) -> List[Dict[str, Any]]:
        hotels = load_mock_json("hotels.json")
        dest = normalise_text(destination)
        selected = [h for h in hotels if normalise_text(h.get("destination")) in {dest, "any"}]
        return selected or hotels

    def normalise_hotels(self, raw_items: List[Dict[str, Any]], destination: Optional[str]) -> List[Dict[str, Any]]:
        normalised = []
        for idx, item in enumerate(raw_items[:5], start=1):
            hotel = item.get("hotel", {})
            offer = (item.get("offers") or [{}])[0]
            price = safe_float((offer.get("price") or {}).get("total"), 150.0)
            normalised.append(
                {
                    "id": f"amadeus_hotel_{idx}",
                    "name": hotel.get("name", f"Amadeus Hotel {idx}"),
                    "destination": destination or "Unknown",
                    "type": "hotel",
                    "nightly_price": price,
                    "eco_rating": 70,
                    "carbon_kg_per_night": 12,
                    "certifications": ["API result, sustainability not verified"],
                    "relevance": 0.70,
                    "description": "Hotel returned by Amadeus sandbox. Sustainability fields are illustrative placeholders.",
                }
            )
        return normalised

    def city_code(self, city: Optional[str]) -> str:
        mapping = {
            "amsterdam": "AMS",
            "berlin": "BER",
            "copenhagen": "CPH",
            "london": "LON",
            "ljubljana": "LJU",
            "vienna": "VIE",
            "paris": "PAR",
            "barcelona": "BCN",
        }
        return mapping.get(normalise_text(city), "AMS")


class RecommendationEngine:
    """Ranks travel options according to carbon, price, and user preference."""

    WEIGHTS = {
        "low": {"carbon": 0.20, "price": 0.55, "preference": 0.25},
        "medium": {"carbon": 0.35, "price": 0.35, "preference": 0.30},
        "high": {"carbon": 0.55, "price": 0.20, "preference": 0.25},
    }

    @classmethod
    def weights_for(cls, sustainability_level: Optional[str]) -> Dict[str, float]:
        return cls.WEIGHTS.get(normalise_text(sustainability_level), cls.WEIGHTS["medium"])

    @staticmethod
    def carbon_score(carbon_kg: float) -> float:
        # Lower emissions should produce a higher score.
        return max(0.0, min(100.0, 100.0 - carbon_kg))

    @staticmethod
    def price_score(price: float, budget: Optional[Any]) -> float:
        budget_value = safe_float(budget, default=800.0) or 800.0
        if price <= budget_value:
            return max(0.0, 100.0 - (price / budget_value) * 35.0)
        overspend_ratio = min(price / budget_value, 3.0)
        return max(0.0, 65.0 - (overspend_ratio - 1.0) * 45.0)

    @staticmethod
    def preference_score(option: Dict[str, Any]) -> float:
        if "eco_rating" in option:
            return float(option.get("eco_rating", 70))
        if "community_benefit" in option:
            return float(option.get("community_benefit", 70))
        return float(option.get("relevance", 0.7)) * 100.0

    @classmethod
    def rank_options(
        cls,
        options: List[Dict[str, Any]],
        sustainability_level: Optional[str],
        budget: Optional[Any],
        option_type: str,
    ) -> List[Dict[str, Any]]:
        weights = cls.weights_for(sustainability_level)
        ranked = []
        for option in options:
            price = float(option.get("price") or option.get("nightly_price") or 0)
            carbon = float(option.get("carbon_kg") or option.get("carbon_kg_per_night") or 0)
            score = (
                weights["carbon"] * cls.carbon_score(carbon)
                + weights["price"] * cls.price_score(price, budget)
                + weights["preference"] * cls.preference_score(option)
            )
            card = {
                "id": option.get("id"),
                "type": option_type,
                "title": option.get("display_name") or option.get("name") or "Recommendation",
                "subtitle": option.get("type") or option.get("mode") or option.get("category") or option_type,
                "price_eur": round(price, 2),
                "carbon_kg": round(carbon, 2),
                "carbon_label": CarbonImpactClassifier.classify(carbon),
                "score": round(score, 2),
                "description": option.get("description", ""),
                "details": option,
            }
            ranked.append(card)
        return sorted(ranked, key=lambda item: item["score"], reverse=True)


def build_context_summary(tracker: Tracker, reason: str) -> Dict[str, Any]:
    """Build a readable handover dictionary for a human advisor."""
    latest_message = tracker.latest_message.get("text") if tracker.latest_message else None
    return {
        "destination": tracker.get_slot("destination"),
        "origin": tracker.get_slot("origin"),
        "travel_date": tracker.get_slot("travel_date"),
        "return_date": tracker.get_slot("return_date"),
        "budget": tracker.get_slot("budget"),
        "sustainability_level": tracker.get_slot("sustainability_level"),
        "preferred_transport": tracker.get_slot("transport_mode"),
        "accommodation_type": tracker.get_slot("accommodation_type"),
        "recommended_options_already_shown": tracker.get_slot("recommended_options"),
        "unresolved_request": latest_message,
        "latest_user_message": latest_message,
        "reason_for_escalation": reason,
    }


class ActionCollectTripPreferences(Action):
    def name(self) -> Text:
        return "action_collect_trip_preferences"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        required_slots = [
            ("destination", "Which destination are you planning to visit?"),
            ("origin", "Where will you travel from?"),
            ("travel_date", "What is your departure date?"),
            ("return_date", "What is your return date?"),
            ("budget", "What is your approximate budget?"),
            ("sustainability_level", "Should sustainability preference be low, medium, or high?"),
        ]
        for slot_name, question in required_slots:
            if not tracker.get_slot(slot_name):
                dispatcher.utter_message(text=question)
                return []

        dispatcher.utter_message(text="Thank you. I have enough information to prepare sustainable recommendations.")
        summary = (
            f"Trip summary: {tracker.get_slot('origin')} to {tracker.get_slot('destination')}, "
            f"from {tracker.get_slot('travel_date')} to {tracker.get_slot('return_date')}, "
            f"budget {tracker.get_slot('budget')}, sustainability preference {tracker.get_slot('sustainability_level')}."
        )
        dispatcher.utter_message(text=summary)
        return []


class ActionRecommendTransport(Action):
    def name(self) -> Text:
        return "action_recommend_transport"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        origin = tracker.get_slot("origin")
        destination = tracker.get_slot("destination")
        budget = tracker.get_slot("budget")
        sustainability_level = tracker.get_slot("sustainability_level")
        requested_mode = normalise_text(tracker.get_slot("transport_mode"))

        transport_options = load_mock_json("transport_options.json")
        if requested_mode:
            transport_options = [opt for opt in transport_options if normalise_text(opt.get("mode")) == requested_mode] or transport_options

        climatiq = ClimatiqClient()
        enriched_options = []
        for option in transport_options:
            estimate = climatiq.estimate_transport(option.get("mode", "train"), origin=origin, destination=destination)
            enriched = dict(option)
            enriched["carbon_kg"] = estimate["carbon_kg"]
            enriched["carbon_source"] = estimate["source"]
            enriched["fallback_reason"] = estimate["fallback_reason"]
            enriched_options.append(enriched)

        cards = RecommendationEngine.rank_options(enriched_options, sustainability_level, budget, "transport")[:3]
        dispatcher.utter_message(
            text="Here are the best transport options ranked by carbon impact, price, and your sustainability preference.",
            json_message={"cards": cards},
        )
        return [SlotSet("recommended_options", {"transport": cards}), SlotSet("selected_option", cards[0] if cards else None)]


class ActionCalculateCarbonFootprint(Action):
    def name(self) -> Text:
        return "action_calculate_carbon_footprint"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        mode = tracker.get_slot("transport_mode") or "train"
        origin = tracker.get_slot("origin")
        destination = tracker.get_slot("destination")
        estimate = ClimatiqClient().estimate_transport(mode, origin=origin, destination=destination)
        label = CarbonImpactClassifier.classify(estimate["carbon_kg"])
        fallback_note = f" Fallback reason: {estimate['fallback_reason']}." if estimate.get("fallback_reason") else ""
        dispatcher.utter_message(
            text=(
                f"Estimated carbon footprint for {estimate['mode']}: {estimate['carbon_kg']} kg CO2e "
                f"for approximately {estimate['distance_km']} km. Carbon label: {label}.{fallback_note}"
            ),
            json_message={"carbon_label": label, "estimate": estimate},
        )
        return [SlotSet("carbon_score", estimate["carbon_kg"])]


class ActionRecommendHotels(Action):
    def name(self) -> Text:
        return "action_recommend_hotels"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        destination = tracker.get_slot("destination")
        accommodation_type = normalise_text(tracker.get_slot("accommodation_type"))
        budget = tracker.get_slot("budget")
        sustainability_level = tracker.get_slot("sustainability_level")

        hotels = AmadeusClient().search_hotels(destination)
        if accommodation_type:
            filtered = [h for h in hotels if accommodation_type in normalise_text(h.get("type"))]
            hotels = filtered or hotels

        cards = RecommendationEngine.rank_options(hotels, sustainability_level, budget, "accommodation")[:3]
        dispatcher.utter_message(
            text="Here are sustainable accommodation recommendations.",
            json_message={"cards": cards},
        )
        return [SlotSet("recommended_options", {"accommodation": cards}), SlotSet("selected_option", cards[0] if cards else None)]


class ActionRecommendCulturalExperiences(Action):
    def name(self) -> Text:
        return "action_recommend_cultural_experiences"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        destination = normalise_text(tracker.get_slot("destination"))
        budget = tracker.get_slot("budget")
        sustainability_level = tracker.get_slot("sustainability_level")
        experiences = load_mock_json("cultural_experiences.json")
        selected = [e for e in experiences if normalise_text(e.get("destination")) in {destination, "any"}]
        if not selected:
            selected = experiences
        cards = RecommendationEngine.rank_options(selected, sustainability_level, budget, "cultural_experience")[:3]
        dispatcher.utter_message(
            text="Here are responsible cultural experiences that support local value creation.",
            json_message={"cards": cards},
        )
        return [SlotSet("recommended_options", {"cultural_experiences": cards}), SlotSet("selected_option", cards[0] if cards else None)]


class ActionRankSustainableOptions(Action):
    def name(self) -> Text:
        return "action_rank_sustainable_options"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        budget = tracker.get_slot("budget")
        sustainability_level = tracker.get_slot("sustainability_level")
        options = load_mock_json("transport_options.json") + AmadeusClient().mock_hotels(tracker.get_slot("destination"))
        cards = RecommendationEngine.rank_options(options, sustainability_level, budget, "mixed")[:5]
        dispatcher.utter_message(
            text="I ranked the available sustainable options using carbon, price, and preference fit.",
            json_message={"cards": cards},
        )
        return [SlotSet("recommended_options", {"mixed": cards})]


class ActionPackageHandoverContext(Action):
    def name(self) -> Text:
        return "action_package_handover_context"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        summary = build_context_summary(tracker, reason="User requested human handover or clarification failed")
        dispatcher.utter_message(
            text="I have packaged your trip context for a human advisor.",
            json_message={"handover_required": True, "handover_context": summary},
        )
        return [SlotSet("handover_required", True), SlotSet("conversation_summary", summary)]


class ActionDefaultFallback(Action):
    def name(self) -> Text:
        return "action_default_fallback"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(
            text="I did not understand that clearly. Please ask about transport, hotels, carbon footprint, cultural experiences, or human handover."
        )
        return [SlotSet("clarification_attempts", 1)]


class ActionTwoStageClarification(Action):
    def name(self) -> Text:
        return "action_two_stage_clarification"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        attempts = int(tracker.get_slot("clarification_attempts") or 0)
        if attempts < 1:
            dispatcher.utter_message(
                text="I am not fully sure what you need. Please choose one option: transport, hotels, carbon footprint, cultural activities, or human advisor.",
                buttons=[
                    {"title": "Transport", "payload": "/ask_transport_options"},
                    {"title": "Hotels", "payload": "/ask_accommodation_options"},
                    {"title": "Carbon footprint", "payload": "/ask_carbon_footprint"},
                    {"title": "Cultural experiences", "payload": "/ask_cultural_experiences"},
                    {"title": "Human advisor", "payload": "/request_human_handover"},
                ],
            )
            return [SlotSet("clarification_attempts", 1)]

        dispatcher.utter_message(text="I am still not confident about your request, so I will prepare a human handover context.")
        return [
            SlotSet("clarification_attempts", 0),
            SlotSet("handover_required", True),
            FollowupAction("action_package_handover_context"),
        ]
