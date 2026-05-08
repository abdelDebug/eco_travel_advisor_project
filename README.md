# Eco Travel Advisor developed by Dr. Abdelaziz Triki

## Project overview

Eco Travel Advisor is a Rasa Open Source chatbot for the MSc assignment titled **Eco Travel Advisor: Conversational Agent for Sustainable Tourism Planning using the Rasa Platform**.

The assistant helps users plan sustainable trips by recommending lower carbon transport, eco friendly accommodation, responsible cultural experiences, and carbon offset options. It includes custom Python actions, mock data fallbacks, external API integration structure, fallback clarification, human advisor handover, tests, Docker deployment, and a simple Streamlit frontend.

## Assignment alignment

| Requirement | Where implemented |
|---|---|
| Rasa Open Source | `config.yml`, `domain.yml`, `data/` |
| Rasa NLU and Rasa Core | NLU examples, stories, rules, slots, policies |
| Multi turn dialogue with slots | `domain.yml`, `data/stories.yml`, `ActionCollectTripPreferences` |
| Custom actions | `actions/actions.py` |
| Climatiq and Amadeus integration structure | `ClimatiqClient`, `AmadeusClient` |
| Mock fallback data | `actions/mock_data/` |
| Two stage fallback | `ActionTwoStageClarification` |
| Human advisor handover | `ActionPackageHandoverContext` |
| Frontend | `frontend/streamlit_app.py`, `frontend/webchat_index.html` |
| Testing | `data/tests/test_stories.yml`, `tests/test_actions.py` |
| Docker deployment | `docker/` |
| Documentation | `README.md`, `docs/` |

## System architecture

1. **Rasa NLU layer** identifies user intents and extracts entities such as destination, origin, dates, budget, transport mode, and sustainability level.
2. **Rasa Core dialogue layer** uses stories, rules, slots, and policies to manage multi turn conversations.
3. **Custom action server** performs recommendation ranking, carbon estimation, fallback logic, and human handover packaging.
4. **External API layer** provides placeholders for Climatiq and Amadeus, with robust fallback to local JSON data.
5. **Frontend layer** offers a Streamlit interface and a Rasa Webchat HTML alternative.

## Setup instructions

Recommended environment: Python 3.10.

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

## Environment variables

Copy the example file:

```bash
cp .env.example .env
```

Then add API keys if available:

```bash
CLIMATIQ_API_KEY=your_key_here
AMADEUS_CLIENT_ID=your_client_id_here
AMADEUS_CLIENT_SECRET=your_client_secret_here
```

The chatbot works without these keys by using local mock data.

## Train the model

```bash
rasa data validate
rasa train
```

## Run the action server

Open a first terminal:

```bash
rasa run actions
```

The action server runs on `http://localhost:5055`.

## Run the Rasa server

Open a second terminal:

```bash
rasa run --enable-api --cors "*" --debug
```

The Rasa REST webhook runs on:

```text
http://localhost:5005/webhooks/rest/webhook
```

## Run the frontend

Open a third terminal:

```bash
streamlit run frontend/streamlit_app.py
```

Then open:

```text
http://localhost:8501
```

## Try one complete conversation

Example:

```text
User: Hello
Bot: Hello. I am your Eco Travel Advisor...
User: I want to plan a sustainable trip
Bot: Which destination are you planning to visit?
User: I want to visit Amsterdam
Bot: Where will you travel from?
User: I am travelling from Berlin
Bot: What are your travel dates?
User: from 12 June to 15 June
Bot: What is your approximate travel budget?
User: my budget is 700 euros
Bot: How strong is your sustainability preference: low, medium, or high?
User: high
User: show me low carbon transport options
Bot: Provides ranked transport recommendation cards.
```

## Testing commands

```bash
rasa data validate
rasa train
rasa test nlu
rasa test core --stories data/tests/test_stories.yml
pytest tests/test_actions.py
```

## Docker deployment

Build and start all services. The Rasa container validates training data, trains a model, then starts the server with Docker specific action endpoint settings:

```bash
docker compose -f docker/docker-compose.yml up --build
```

Services:

| Service | Port |
|---|---:|
| Rasa server | 5005 |
| Action server | 5055 |
| Streamlit frontend | 8501 |

For a faster repeat run, keep the generated `models/` folder mounted through Docker Compose.

## Limitations

This is an academic prototype. Climatiq and Amadeus integrations include defensive placeholder logic and mock fallback data. Real sustainability certifications, live pricing, availability, accessibility details, and carbon factors should be verified before real user deployment.

## Ethical considerations

The assistant should not present mock recommendations as real bookings. It should explain carbon estimates as approximate. It should avoid greenwashing by showing why each option is considered sustainable and where the data came from.

## GDPR and privacy notes

The prototype should collect only travel planning data needed for the conversation. API keys must be stored in environment variables. Do not commit `.env`. Do not ask users for passport numbers, payment details, medical details, or other sensitive information.

## Accessibility considerations

The frontend uses text labels in addition to colour coded carbon indicators. Students should test keyboard navigation, readable contrast, screen reader compatibility, and clear error messages.
