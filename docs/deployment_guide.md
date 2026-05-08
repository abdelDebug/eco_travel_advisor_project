# Deployment Guide

## 1. Local deployment

Install dependencies:

```bash
pip install -r requirements.txt
```

Validate and train:

```bash
rasa data validate
rasa train
```

Terminal 1:

```bash
rasa run actions
```

Terminal 2:

```bash
rasa run --enable-api --cors "*" --debug
```

Terminal 3:

```bash
streamlit run frontend/streamlit_app.py
```

## 2. Docker deployment

Build and start. The Docker Rasa service uses `docker/endpoints.docker.yml` so that the Rasa container can reach the action server by service name:

```bash
docker compose -f docker/docker-compose.yml up --build
```

Expected services:

- Rasa server, port 5005
- Action server, port 5055
- Streamlit frontend, port 8501

## 3. Hugging Face Spaces deployment

A simple approach is to deploy only the Streamlit frontend to Hugging Face Spaces and connect it to an externally hosted Rasa REST endpoint.

Steps:

1. Create a new Space using the Streamlit SDK.
2. Add `frontend/streamlit_app.py` as the app file.
3. Add required dependencies to `requirements.txt`.
4. Set `RASA_REST_URL` as a Space secret.
5. Host the Rasa server and action server separately using a VM, Docker host, or cloud service.

For a full all in one deployment, use Docker on a VM instead of basic Spaces because Rasa, action server, and Streamlit normally run as separate services.

## 4. Environment variable management

Use `.env` locally. In Docker Compose, use an environment file or deployment secrets.

Never commit:

- Climatiq API keys
- Amadeus client ID
- Amadeus client secret
- production webhook secrets

## 5. API key security

Good practice:

- store keys in environment variables
- rotate keys after demonstrations
- restrict API keys where the provider supports restrictions
- never print keys in logs
- never include keys in screenshots submitted for coursework

## 6. Endpoint configuration

`endpoints.yml` points Rasa to the action server:

```yaml
action_endpoint:
  url: "http://localhost:5055/webhook"
```

Inside Docker Compose, service names can be used instead of localhost when needed, for example:

```yaml
action_endpoint:
  url: "http://action_server:5055/webhook"
```

If you run into connection issues, check that the action server is running before starting the Rasa server.
