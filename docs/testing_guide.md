# Testing Guide

## 1. Data validation

Run:

```bash
rasa data validate
```

This checks whether the domain, NLU data, stories, and rules are structurally consistent.

## 2. NLU testing

Run:

```bash
rasa test nlu
```

Recommended checks:

- The assistant recognises trip planning requests.
- Destination, origin, date, budget, sustainability level, transport mode, and accommodation entities are extracted.
- Ambiguous and unrelated examples trigger fallback or out of scope behaviour.

## 3. Core dialogue testing

Train first:

```bash
rasa train
```

Then run:

```bash
rasa test core --stories data/tests/test_stories.yml
```

Recommended checks:

- The bot asks missing trip details in a logical order.
- Direct questions such as carbon footprint and accommodation recommendation trigger the correct actions.
- Human handover is triggered when requested.
- The fallback flow uses clarification before escalation.

## 4. Action testing

Run:

```bash
pytest tests/test_actions.py
```

The tests cover:

- recommendation ranking
- Climatiq API fallback behaviour
- hotel recommendation card generation
- handover context packaging
- two stage clarification escalation

## 5. User testing

Ask several users to complete these tasks:

1. Plan a short city break.
2. Compare train and flight emissions.
3. Find eco accommodation.
4. Ask for cultural experiences.
5. Enter an ambiguous message and check whether the bot clarifies.
6. Request a human advisor.

Collect feedback on clarity, usefulness, trust, and perceived sustainability relevance.

## 6. Recommendation quality evaluation

Suggested evaluation criteria:

| Criterion | Question |
|---|---|
| Carbon relevance | Does the bot prefer lower carbon choices when sustainability is high? |
| Price relevance | Does the bot consider budget limits? |
| Transparency | Does the bot explain why an option is recommended? |
| Robustness | Does the bot still work without API keys? |
| Academic clarity | Can a student explain the scoring formula and fallback design? |

## 7. UI and accessibility testing

Check:

- readable labels
- keyboard usability
- text alternatives for carbon colours
- clear error messages when Rasa is offline
- privacy notice visibility
- human handover indicator visibility
