# Architecture Guide

## 1. Rasa NLU layer

The NLU layer is defined in `data/nlu.yml` and configured in `config.yml`. It detects intents such as trip planning, transport recommendation, accommodation recommendation, carbon footprint calculation, privacy notice, accessibility support, and human handover. It extracts entities including destination, origin, travel dates, budget, sustainability level, transport mode, accommodation type, and user location.

The NLU pipeline uses tokenisation, feature extraction, DIET classification, entity synonym handling, response selection, and a fallback classifier.

## 2. Rasa Core dialogue layer

The Core layer is defined through:

- `domain.yml`, which declares intents, entities, slots, responses, and actions.
- `data/stories.yml`, which provides multi turn conversation paths.
- `data/rules.yml`, which provides deterministic behaviour for greetings, fallback, handover, privacy notice, and direct recommendation requests.

Slots hold the conversation memory needed for sustainable travel planning.

## 3. Custom action server

The custom action server is implemented in `actions/actions.py`. It contains:

- `ActionCollectTripPreferences`, checks missing trip details.
- `ActionRecommendTransport`, ranks transport modes.
- `ActionCalculateCarbonFootprint`, estimates emissions.
- `ActionRecommendHotels`, recommends sustainable accommodation.
- `ActionRecommendCulturalExperiences`, recommends responsible activities.
- `ActionRankSustainableOptions`, demonstrates combined scoring.
- `ActionPackageHandoverContext`, prepares human advisor context.
- `ActionTwoStageClarification`, implements fallback escalation.

## 4. External APIs

### Climatiq

`ClimatiqClient` reads `CLIMATIQ_API_KEY` from environment variables. It estimates carbon impact for train, bus, flight, car, walking, and cycling. If the key is missing, the request times out, an invalid response is returned, or the API limit is reached, it uses mock emission factors.

### Amadeus

`AmadeusClient` reads `AMADEUS_CLIENT_ID` and `AMADEUS_CLIENT_SECRET`. It includes token retrieval and placeholder hotel and flight search methods. If credentials are unavailable or requests fail, it falls back to `actions/mock_data/`.

## 5. Mock database fallback

The mock database is stored in JSON files:

- `hotels.json`
- `transport_options.json`
- `cultural_experiences.json`
- `carbon_offsets.json`

This ensures the assistant can run locally without paid or external services.

## 6. Recommendation engine

The recommendation engine combines:

- carbon impact score
- price score
- user preference match score

The score is calculated as:

```text
final_score = carbon_weight * carbon_score + price_weight * price_score + preference_weight * preference_match_score
```

Weights change depending on sustainability level:

| Sustainability level | Scoring behaviour |
|---|---|
| Low | price receives stronger weight |
| Medium | carbon, price, and preference are balanced |
| High | carbon receives strongest weight |

## 7. Frontend layer

The Streamlit frontend calls the Rasa REST webhook at:

```text
http://localhost:5005/webhooks/rest/webhook
```

It displays chat messages, recommendation cards, colour and text carbon labels, privacy information, accessibility information, and handover context.

The Webchat HTML option gives students an alternative integration path.

## 8. Human handover flow

The handover action packages:

- destination
- origin
- dates
- budget
- sustainability level
- preferred transport
- accommodation type
- recommendations already shown
- latest user message
- reason for escalation

This creates a readable context object for a human travel advisor.
