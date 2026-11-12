# IMPORTANT ! DO NOT MODIFY THIS FILE, YOU CAN COPY COMMANDS FROM THIS FILE AND EXECUTE IN TERMINAL

- All commands mentioned here need to be run in the terminal from the `task` folder. Do not paste them into any files.

## Install Requirements

```bash
# From the repository root, create and activate the environment first:
# python3 -m venv .venv
# source .venv/bin/activate
# cd task
python3 -m pip install -r requirements.txt
```

## Start the API

```bash
python3 -m uvicorn shoplite.main:app --app-dir src --reload --port 8000
```

## Try the API

```bash
# Log in and keep the token
TOKEN=$(curl -s -X POST localhost:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email": "alice@shoplite.test", "password": "password123"}' | python3 -c 'import sys, json; print(json.load(sys.stdin)["token"])')

curl -s "localhost:8000/api/products?q=bottle"
curl -s -X POST localhost:8000/api/cart/items -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"product_id": 1, "quantity": 2}'
curl -s localhost:8000/api/cart -H "Authorization: Bearer $TOKEN"
curl -s -X POST localhost:8000/api/checkout -H "Authorization: Bearer $TOKEN" -H 'Idempotency-Key: my-first-order'
curl -s "localhost:8000/api/orders?page=1" -H "Authorization: Bearer $TOKEN"
```

## Running All Unit Tests

```bash
python3 -m pytest tests/test_main.py
```

## Running Specific Unit Test

```bash
python3 -m pytest tests/test_main.py -k test_name
```

### Example

```bash
python3 -m pytest tests/test_main.py -k pagination
```
