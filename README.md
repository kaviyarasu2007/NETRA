# Netra Storage Monitor

Netra Storage Monitor is a local file upload and download project with an approval-based workflow. The public storage site is served by Python, incoming requests are exposed through ngrok, and a separate Streamlit dashboard lets an operator approve or reject requests before the server completes them.[1][2][3]

## Project overview

The project is split into two running apps plus an ngrok tunnel.[1][4]

- `server.py` runs the storage site and waits for approval before responding to upload or download requests.[4][3]
- `monitor.py` runs the Streamlit dashboard and shows pending and recent requests from the shared SQLite database.[5][6][3]
- `site/index.html` is the public-facing storage page for file upload and file listing.[1]
- `approvals.db` is the SQLite database that stores request state, including pending, allowed, rejected, and timed-out requests.[3]
- `uploads/` stores uploaded files after an operator allows the request.[1]

## Architecture

The request flow is:

`Visitor -> ngrok public URL -> server.py -> approvals.db -> monitor.py decision -> server.py response`.[3][7]

This architecture solves two practical issues: the Streamlit UI can refresh on a timer using fragments, and the server can delay its response until the approval decision is written to SQLite.[5][6][3]

## Features

- Approval-based upload and download handling through the monitor dashboard.[1]
- Real-time or near-real-time request visibility in Streamlit using timed reruns.[5][6]
- Public tunnel exposure using ngrok for testing from outside the local machine.[8][7]
- Simple file storage using a local uploads directory and a lightweight Python HTTP server.[4]
- Shared local state using SQLite, which is included with Python and does not require a separate database server.[3]

## Folder structure

```text
ngrok-file-lab/
├── server.py
├── monitor.py
├── requirements.txt
├── approvals.db
├── uploads/
└── site/
    └── index.html
```

## Requirements

Install the following before running the project:[9][3]

- Python 3
- ngrok
- `streamlit`
- `pandas`

A virtual environment is recommended for isolation.[9]

## Installation

Create a project folder, create a virtual environment, activate it, and install the Python packages.[9]

```bash
mkdir ngrok-file-lab
cd ngrok-file-lab
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install streamlit pandas
```

If the code files are already present, ensure this structure exists:[2]

```text
server.py
monitor.py
site/index.html
```

## Run the project

Open three terminals and run the components in this order.[2][8][9]

### 1. Start the server

```bash
cd ~/ngrok-file-lab
source .venv/bin/activate
python3 server.py
```

The storage site will listen on port 8000.[1]

### 2. Start the monitor dashboard

```bash
cd ~/ngrok-file-lab
source .venv/bin/activate
streamlit run monitor.py
```

If `streamlit` is not found in the shell, use the module form instead.[9]

```bash
python3 -m streamlit run monitor.py
```

### 3. Start ngrok

```bash
cd ~/ngrok-file-lab
ngrok http 8000
```

ngrok will create a public URL that forwards traffic to the local server and makes request inspection available through the local agent interface.[8][7]

## How it works

When a visitor opens the public site or submits an upload or download request, `server.py` records the request in SQLite with a `pending` state and waits for a decision.[3][4]

`monitor.py` reads the same database and displays the pending request list. With Streamlit fragments, the dashboard can rerun on a timer so new requests appear without manual refresh.[5][6]

When the operator clicks **Allow** or **Reject**, the dashboard updates the database row. The waiting request handler reads the decision and either completes the action, blocks it, or times out if no decision arrives in time.[3][4]

## Public routes

The storage server commonly exposes these routes in the project design:[1]

| Route | Method | Purpose |
|------|--------|---------|
| `/` | GET | Show the public storage page and file list. |
| `/upload` | POST | Submit a file upload request for approval. |
| `/files` | GET | Return a JSON list of stored files. |
| `/download/<filename>` | GET | Download a stored file after approval. |

## Expected workflow

1. Open the ngrok public URL in a browser.[8]
2. The visitor requests the site, uploads a file, or downloads a file.[1]
3. The server stores the request as pending in SQLite.[3]
4. The Streamlit monitor shows the pending request and waits for operator action.[5][6]
5. The operator allows or rejects the request.[3]
6. The server sends the final response based on that decision.[4]

## Troubleshooting

### Streamlit does not auto-refresh

Use a fragment-based panel with `run_every` for periodic reruns, because Streamlit does not continuously poll by default.[5][6]

### Requests always time out

This usually means `monitor.py` is not running, the database path differs between the server and monitor, or the monitor is not writing approval actions to the same SQLite file.[3]

### Upload is blocked or rejected

A blocked upload means the operator clicked Reject or no approval was received within the configured timeout window.[3]

### `IndentationError` in `server.py`

Python requires an indented block after statements such as `if`, `for`, `def`, and `class`. This error is commonly caused by a bad paste or mixed tabs and spaces.[10][11]

## Security notes

This project is useful for local demos, traffic labs, and approval-flow experiments, but it is still a simple Python HTTP server rather than a hardened production storage platform.[4]

For real deployment, add stronger validation, authentication, file type restrictions, size limits, audit logging, and safer concurrency handling.[3][4]

## Future improvements

- Request search and filtering in the monitor.[2]
- Colored status badges and richer request detail views.[2]
- Request body and header inspection panels.[7]
- Auto-cleanup for expired request records.[3]
- Stronger upload validation and file restrictions.[3]

## License

Use this project as a personal learning or internal lab tool unless a different license is added later.
