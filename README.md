# IoT Smart Home System - Assignment 8

**CECS 327: Introduction to Networking and Distributed Systems**  
California State University, Long Beach  
David Cardenas and Jack McKelvey

---

## Project Overview

This project implements a distributed, end-to-end IoT smart home system spanning two physical households. Virtual IoT sensors on the DataNiz platform stream real-time data into two separate cloud-hosted PostgreSQL databases. A TCP server aggregates and queries both databases to answer distributed queries, and a TCP client provides a simple menu-driven interface for the user.

The system demonstrates key concepts in distributed systems: inter-node data sharing, cross-database querying, partial vs. complete result detection, and time-aware replication boundaries.

---

## System Architecture

```
[House A - David]                        [House B - Jack]
  DataNiz Virtual Devices                  DataNiz Virtual Devices
        |                                          |
        v                                          v
  NeonDB PostgreSQL                         NeonDB PostgreSQL
  (sensor_data_virtual)                     (IoT_Data_virtual)
        |                                          |
        +------------------+   +-----------------+
                           |   |
                           v   v
                       [ server.py ]
                       TCP Server :5000
                           |
                           v
                       [ client.py ]
                       TCP Client
```

**Data flow:**

1. Virtual IoT devices on DataNiz continuously write sensor readings to their respective NeonDB databases.
2. `server.py` maintains connections to both databases and processes incoming query requests over TCP.
3. `client.py` connects to the server on port 5000, presents a query menu, and displays formatted results.
4. For queries that span the data-sharing cutoff, the server queries both databases and merges the results.

---

## Devices and Sensors

### House A (David)

| Device | Board Name | Fields |
|---|---|---|
| Smart Fridge 1 | Fridge-Arduino | moisture (%), thermistor (V), ammeter (A) |
| Smart Fridge 2 | Fridge-Arduino | moisture (%), thermistor (V), ammeter (A) |
| Smart Dishwasher | Dishwasher-Pi | water-consumption (liters), dishwasher-ammeter (A) |
| Electricity Meter | (filtered by topic/email) | electricity reading (watts) |

### House B (Jack)

| Device | Board Name | Fields |
|---|---|---|
| Smart Fridge | HouseB_Fridge_Board | HouseB_Fridge_Board_Sensor (moisture %) |
| Smart Dishwasher | HouseB_Dishwasher_Board | HouseB_Dishwasher_Board_Sensor (liters) |
| Electricity Meter | HouseB_Electricty_Meter_Board | HouseB_Electricty_Meter_Board_Sensor (watts) |

---

## How to Run

### Requirements

- Python 3
- `psycopg2-binary` library

### Installation

```bash
pip install psycopg2-binary
```

### Starting the Server

Open a terminal and run:

```bash
# macOS / Linux
python3 server.py

# Windows
python server.py
```

The server will start listening on port 5000.

### Starting the Client

Open a second terminal and run:

```bash
# macOS / Linux
python3 client.py

# Windows
python client.py
```

The client connects to `127.0.0.1:5000` and presents a menu of available queries. Invalid input is rejected with an error message.

---

## Query Examples

The client menu offers three queries:

**Query 1: Average fridge moisture**
```
What is the average moisture inside our kitchen fridges in the past hours, week and month?
```
Reports average moisture (%) across all fridge sensors in both houses, broken down by the past hour, past week, and past month.

**Query 2: Average dishwasher water consumption**
```
What is the average water consumption per cycle across our smart dishwashers in the past hour, week and month?
```
Reports average water usage per cycle across both dishwashers in liters and gallons, for the past hour, week, and month.

**Query 3: Electricity comparison**
```
Which house consumed more electricity in the past 24 hours, and by how much?
```
Compares total electricity consumption (in kWh) between House A and House B over the past 24 hours, identifying which house used more and by what margin.

---

## Distributed Design and Sharing Model

### Data Sharing Cutoff

Data sharing between the two houses began on **April 29, 2026 at 9:30 PM PDT** (April 30, 2026 at 04:30 UTC).

From this point forward, Jack's sensor data is replicated into David's NeonDB database. This is a forward-only replication -- historical data from before the sharing cutoff remains only in Jack's database.

### Query Window Logic

The server checks whether a query's time window crosses the sharing start time:

- **Post-sharing window only** (query range is entirely after the cutoff): the server queries only David's database, since it already contains Jack's data. Result is labeled **COMPLETE**.
- **Window crosses the cutoff** (query range extends before the cutoff): the server queries David's database for post-sharing data and directly queries Jack's database for pre-sharing historical data. Result is labeled **COMPLETE** if both sources are available, or **PARTIAL** if Jack's database is unreachable or lacks the required historical data.
- **Pre-sharing window only**: the server queries Jack's database directly for House B data and David's database for House A data. Result is labeled based on availability.

This design minimizes redundant cross-database connections while ensuring historical queries are filled accurately.

---

## Data Structure

Query results are accumulated using a custom linked list class. Each node in the list holds one line of formatted output. The server traverses the linked list to assemble the full response string, which is then sent back to the client over TCP.

This structure makes it straightforward to append result lines incrementally as each sub-query (hour, week, month) completes, without pre-allocating a fixed-size buffer.

---

## Metadata Usage

### Board Name

The `board_name` field in each database record identifies which house and device type a reading belongs to. The server uses `board_name` to filter records by device category when computing averages:

- Fridge readings: matched on `Fridge-Arduino` (House A) and `HouseB_Fridge_Board` (House B)
- Dishwasher readings: matched on `Dishwasher-Pi` (House A) and `HouseB_Dishwasher_Board` (House B)
- Electricity readings: matched on `HouseB_Electricty_Meter_Board` (House B)

### Topic Field

House A electricity data is filtered using the `topic` field, which contains the owner's email address. This distinguishes House A electricity meter records from other device records that share the same database.

---

## Calculations and Conversions

| Measurement | Conversion |
|---|---|
| Water (liters to gallons) | gallons = liters x 0.264172 |
| Electricity (watts to kWh) | kWh = average_watts x 24 / 1000 |

All timestamps are stored in UTC in both databases. The server converts them to **PDT (UTC-7)** for display in query results.

---

## Team

| Name | House | Role |
|---|---|---|
| David Cardenas | House A | Server, database design, distributed query logic |
| Jack McKelvey | House B | Sensor setup, database setup, data sharing |

**Course:** CECS 327 - Introduction to Networking and Distributed Systems  
**Institution:** California State University, Long Beach
