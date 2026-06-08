# Triemli Tram 14 Delay Collector

Collect live delay observations for tram line 14 at `Zürich, Triemli` from the search.ch stationboard API, store them in PostgreSQL, and report how often observed departures were delayed.

The search.ch API exposes current delay data with `show_delays=1`, but it does not provide archived delay observations for arbitrary past dates. To calculate a real seven-day delay percentage, run the collector continuously for seven days.

## Setup

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up -d
.\.venv\Scripts\python.exe main.py init-db
```

The default database URL is:

```text
postgresql://triemli:triemli@localhost:5432/triemli_delays
```

Override it with `DATABASE_URL` if needed.

## Usage

Collect one snapshot:

```powershell
.\.venv\Scripts\python.exe main.py collect-once
```

Collect every five minutes for seven days:

```powershell
.\.venv\Scripts\python.exe main.py collect-loop
```

Calculate the delay percentage from the last seven days:

```powershell
.\.venv\Scripts\python.exe main.py report
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```
