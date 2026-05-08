"""Simple Streamlit frontend for the Eco Travel Advisor Rasa bot."""

import json
import os
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

RASA_REST_URL = os.getenv("RASA_REST_URL", "http://localhost:5005/webhooks/rest/webhook")

st.set_page_config(page_title="Eco Travel Advisor", layout="centered")
st.title("Eco Travel Advisor")
st.caption("Sustainable tourism planning with Rasa, custom actions, carbon labels, and human handover support.")


def send_to_rasa(sender_id: str, message: str) -> List[Dict[str, Any]]:
    payload = {"sender": sender_id, "message": message}
    try:
        response = requests.post(RASA_REST_URL, json=payload, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return [{"text": f"Could not reach Rasa server at {RASA_REST_URL}. Error: {exc}"}]


def label_badge(label: str) -> str:
    label = (label or "unknown").lower()
    return {
        "green": "[GREEN] LOW IMPACT",
        "amber": "[AMBER] MEDIUM IMPACT",
        "red": "[RED] HIGH IMPACT",
    }.get(label, "[UNKNOWN] IMPACT")


def append_assistant_response(response: Dict[str, Any]) -> None:
    st.session_state.messages.append(
        {
            "role": "assistant",
            "text": response.get("text"),
            "custom": response.get("custom") or {},
            "buttons": response.get("buttons") or [],
        }
    )


def bootstrap_conversation() -> None:
    for response in send_to_rasa(st.session_state.sender_id, "/greet"):
        append_assistant_response(response)
    st.session_state.bootstrapped = True


def reset_conversation() -> None:
    st.session_state.sender_id = f"streamlit_{uuid.uuid4().hex}"
    st.session_state.messages = []
    st.session_state.pending_user_message = None
    st.session_state.bootstrapped = False


def queue_user_message(raw_message: str, display_message: Optional[str] = None) -> None:
    st.session_state.pending_user_message = {
        "raw": raw_message,
        "display": display_message if display_message is not None else raw_message,
    }


def handle_user_message(raw_message: str, display_message: Optional[str] = None) -> None:
    st.session_state.messages.append(
        {
            "role": "user",
            "text": display_message if display_message is not None else raw_message,
        }
    )

    for response in send_to_rasa(st.session_state.sender_id, raw_message):
        append_assistant_response(response)


def build_intent_payload(intent_name: str, entities: Dict[str, Any]) -> str:
    return f"/{intent_name}{json.dumps(entities, ensure_ascii=True)}"


def get_latest_assistant_message() -> Optional[Dict[str, Any]]:
    for message in reversed(st.session_state.messages):
        if message.get("role") == "assistant":
            return message
    return None


def expected_prompt_type(message: Dict[str, Any]) -> Optional[str]:
    text = (message.get("text") or "").lower()
    if "which destination are you planning to visit" in text:
        return "destination"
    if "where will you travel from" in text:
        return "origin"
    if "travel dates" in text or ("departure date" in text and "return date" in text):
        return "date_range"
    if "what is your departure date" in text:
        return "travel_date"
    if "what is your return date" in text:
        return "return_date"
    if "what is your approximate travel budget" in text or "what is your approximate budget" in text:
        return "budget"
    if "how strong is your sustainability preference" in text or "should sustainability preference be" in text:
        return "sustainability_level"
    return None


def build_prompt_response(message: Optional[Dict[str, Any]], user_text: str) -> Dict[str, str]:
    cleaned_text = user_text.strip()
    prompt_type = expected_prompt_type(message or {})

    if prompt_type == "destination":
        return {"raw": build_intent_payload("provide_destination", {"destination": cleaned_text}), "display": cleaned_text}
    if prompt_type == "origin":
        return {"raw": build_intent_payload("provide_origin", {"origin": cleaned_text}), "display": cleaned_text}
    if prompt_type == "travel_date":
        return {"raw": build_intent_payload("provide_dates", {"travel_date": cleaned_text}), "display": cleaned_text}
    if prompt_type == "return_date":
        return {"raw": build_intent_payload("provide_dates", {"return_date": cleaned_text}), "display": cleaned_text}
    if prompt_type == "budget":
        return {"raw": build_intent_payload("provide_budget", {"budget": cleaned_text}), "display": cleaned_text}
    if prompt_type == "sustainability_level":
        normalized_text = cleaned_text.lower()
        if normalized_text in {"low", "medium", "high"}:
            return {
                "raw": build_intent_payload(
                    "provide_sustainability_preference",
                    {"sustainability_level": normalized_text},
                ),
                "display": cleaned_text,
            }

    return {"raw": cleaned_text, "display": cleaned_text}


def queue_prompt_response(user_text: str) -> None:
    structured_message = build_prompt_response(get_latest_assistant_message(), user_text)
    queue_user_message(structured_message["raw"], display_message=structured_message["display"])


def format_date_range_display(start_date: date, end_date: date) -> str:
    return f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"


def format_single_date_message(selected_date: date) -> str:
    return selected_date.strftime("%d %B %Y")


def format_single_date_display(selected_date: date) -> str:
    return selected_date.strftime("%d %b %Y")


def render_cards(cards: List[Dict[str, Any]]) -> None:
    for card in cards:
        with st.container(border=True):
            st.subheader(card.get("title", "Recommendation"))
            st.write(card.get("description", ""))
            col1, col2, col3 = st.columns(3)
            col1.metric("Estimated price", f"EUR {card.get('price_eur', 0)}")
            col2.metric("Carbon", f"{card.get('carbon_kg', 0)} kg CO2e")
            col3.metric("Score", card.get("score", 0))
            st.write(f"Carbon label: {label_badge(card.get('carbon_label'))}")


def render_date_picker(message_index: int, prompt_type: str) -> None:
    default_departure = date.today() + timedelta(days=14)
    default_return = default_departure + timedelta(days=3)

    if prompt_type == "date_range":
        with st.form(key=f"travel_dates_form_{message_index}", border=False):
            selected_dates = st.date_input(
                "Select departure and return dates",
                value=(default_departure, default_return),
                min_value=date.today(),
                key=f"travel_dates_{message_index}",
            )
            submitted = st.form_submit_button("Use selected dates")

        if submitted:
            if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
                departure_date, return_date = selected_dates
                queue_user_message(
                    build_intent_payload(
                        "provide_dates",
                        {
                            "travel_date": format_single_date_message(departure_date),
                            "return_date": format_single_date_message(return_date),
                        },
                    ),
                    display_message=format_date_range_display(departure_date, return_date),
                )
                st.rerun()

            st.warning("Please select both a departure date and a return date.")
        return

    field_name = "departure" if prompt_type == "travel_date" else "return"
    button_label = f"Use selected {field_name} date"

    with st.form(key=f"{prompt_type}_form_{message_index}", border=False):
        selected_date = st.date_input(
            f"Select {field_name} date",
            value=default_departure if prompt_type == "travel_date" else default_return,
            min_value=date.today(),
            key=f"{prompt_type}_{message_index}",
        )
        submitted = st.form_submit_button(button_label)

    if submitted:
        queue_user_message(
            build_intent_payload("provide_dates", {prompt_type: format_single_date_message(selected_date)}),
            display_message=format_single_date_display(selected_date),
        )
        st.rerun()


def render_assistant_message(message: Dict[str, Any], message_index: int, is_active_turn: bool) -> None:
    with st.chat_message("assistant"):
        if message.get("text"):
            st.write(message["text"])

        custom = message.get("custom") or {}
        if custom.get("cards"):
            render_cards(custom["cards"])
        if custom.get("handover_required"):
            st.warning("Human handover requested. A context package has been prepared for the advisor.")
            st.json(custom.get("handover_context", {}))
        if custom.get("carbon_label"):
            st.info(f"Carbon label: {label_badge(custom['carbon_label'])}")

        prompt_type = expected_prompt_type(message)
        if is_active_turn and prompt_type in {"date_range", "travel_date", "return_date"}:
            render_date_picker(message_index, prompt_type)

        for button_index, button in enumerate(message.get("buttons") or []):
            payload = button.get("payload", button.get("title", ""))
            title = button.get("title", "Option")
            key = f"button_{message_index}_{button_index}_{payload}"
            if st.button(title, key=key):
                queue_user_message(payload, display_message=title)


if "sender_id" not in st.session_state:
    st.session_state.sender_id = f"streamlit_{uuid.uuid4().hex}"

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_user_message" not in st.session_state:
    st.session_state.pending_user_message = None

if "bootstrapped" not in st.session_state:
    st.session_state.bootstrapped = False

if not st.session_state.bootstrapped:
    bootstrap_conversation()

with st.expander("Privacy notice", expanded=False):
    st.write(
        "This academic prototype uses only the trip information you type into the chat. "
        "Do not enter sensitive personal data. API keys belong in environment variables, not in the source code."
    )

with st.expander("Accessibility support", expanded=False):
    st.write("Carbon labels are shown as text. Buttons are optional because all actions can also be typed as plain text.")

if st.button("Start new conversation", key="reset_conversation"):
    reset_conversation()
    st.rerun()

for index, message in enumerate(st.session_state.messages):
    if message["role"] == "user":
        st.chat_message("user").write(message["text"])
    else:
        render_assistant_message(message, index, is_active_turn=index == len(st.session_state.messages) - 1)

prompt = st.chat_input("Ask about sustainable transport, eco hotels, carbon footprint, or local experiences")
if prompt:
    queue_prompt_response(prompt)

pending = st.session_state.pending_user_message
if pending:
    st.session_state.pending_user_message = None
    handle_user_message(pending["raw"], display_message=pending["display"])
    st.rerun()
