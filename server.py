import socket
import json
import traceback
import psycopg2
from datetime import datetime, timezone, timedelta
 
MY_DB_URL = "postgresql://neondb_owner:npg_y8f3sWpMSGrL@ep-royal-moon-amw55zdz-pooler.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
JACK_DB_URL = "postgresql://neondb_owner:npg_cjy1EgY0adOu@ep-holy-hall-anlbzpax-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
 
SHARING_START_UTC = datetime(2026, 4, 30, 4, 30, 0, tzinfo=timezone.utc)
HOUSE_A = "House A (David)"
HOUSE_B = "House B (Jack)"
PDT = timezone(timedelta(hours=-7))
 
class Node:
    def __init__(self, value):
        self.value = value
        self.next = None
 
class LinkedList:
    def __init__(self):
        self.head = None
 
    def append(self, value):
        new_node = Node(value)
        if not self.head:
            self.head = new_node
            return
        curr = self.head
        while curr.next:
            curr = curr.next
        curr.next = new_node
 
    def to_list(self):
        result = []
        curr = self.head
        while curr:
            result.append(curr.value)
            curr = curr.next
        return result
 
def get_conn(url):
    return psycopg2.connect(url)
 
def fetch(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or [])
        return cur.fetchall()
 
def now_utc():
    return datetime.now(timezone.utc)
 
def to_pdt(dt):
    return dt.astimezone(PDT).strftime("%Y-%m-%d %I:%M %p PDT")
 
def parse_payload(row):
    payload = row[0]
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        return json.loads(payload)
    return dict(payload)
 
def query_moisture():
    results = LinkedList()
    now = now_utc()
    windows = {
        "Past Hour":  now - timedelta(hours=1),
        "Past Week":  now - timedelta(weeks=1),
        "Past Month": now - timedelta(days=30),
    }
 
    for label, since in windows.items():
        house_a_vals = []
        house_b_vals = []
 
        # House A — from my DB
        try:
            conn = get_conn(MY_DB_URL)
            rows = fetch(conn, """
                SELECT payload FROM sensor_data_virtual
                WHERE payload::text LIKE '%%moisture%%'
                AND time >= %s
            """, [since])
            for row in rows:
                d = parse_payload(row)
                if "moisture" in d:
                    house_a_vals.append(float(d["moisture"]))
            conn.close()
        except Exception as e:
            traceback.print_exc()
            print(f"[A moisture error] {e}")
 
        # House B post-sharing — from my DB (Jack's data shared to me)
        try:
            conn = get_conn(MY_DB_URL)
            rows = fetch(conn, """
                SELECT payload FROM sensor_data_virtual
                WHERE payload->>'board_name' = 'HouseB_Fridge_Board'
                AND time >= %s
            """, [since])
            for row in rows:
                d = parse_payload(row)
                if "HouseB_Fridge_Board_Sensor" in d:
                    house_b_vals.append(float(d["HouseB_Fridge_Board_Sensor"]))
            conn.close()
        except Exception as e:
            traceback.print_exc()
            print(f"[B moisture post-sharing error] {e}")
 
        # House B pre-sharing — fetch historical gap directly from Jack's DB
        if since < SHARING_START_UTC:
            try:
                conn = get_conn(JACK_DB_URL)
                rows = fetch(conn, """
                    SELECT payload FROM "IoT_Data_virtual"
                    WHERE payload->>'board_name' = 'HouseB_Fridge_Board'
                    AND time >= %s AND time < %s
                """, [since, SHARING_START_UTC])
                pre_count = 0
                for row in rows:
                    d = parse_payload(row)
                    if "HouseB_Fridge_Board_Sensor" in d:
                        house_b_vals.append(float(d["HouseB_Fridge_Board_Sensor"]))
                        pre_count += 1
                conn.close()
                completeness = f"COMPLETE (fetched {pre_count} pre-sharing records from House B DB)"
            except Exception as e:
                traceback.print_exc()
                completeness = f"PARTIAL — pre-sharing fetch failed: {e}"
        else:
            completeness = "COMPLETE (within sharing window)"
 
        all_vals = house_a_vals + house_b_vals
        if all_vals:
            avg = sum(all_vals) / len(all_vals)
            avg_a = sum(house_a_vals)/len(house_a_vals) if house_a_vals else 0
            avg_b = sum(house_b_vals)/len(house_b_vals) if house_b_vals else 0
            results.append(
                f"  {label}:\n"
                f"    Combined Avg: {avg:.2f}%\n"
                f"    {HOUSE_A}: {avg_a:.2f}% ({len(house_a_vals)} readings)\n"
                f"    {HOUSE_B}: {avg_b:.2f}% ({len(house_b_vals)} readings)\n"
                f"    Status: {completeness}"
            )
        else:
            results.append(f"  {label}: No data available")
 
    return "=== Average Moisture in Kitchen Fridges ===\n" + "\n".join(results.to_list())
 
def query_water():
    results = LinkedList()
    now = now_utc()
    windows = {
        "Past Hour":  now - timedelta(hours=1),
        "Past Week":  now - timedelta(weeks=1),
        "Past Month": now - timedelta(days=30),
    }
    L_TO_GAL = 0.264172
 
    for label, since in windows.items():
        house_a_vals = []
        house_b_vals = []
 
        # House A — from my DB
        try:
            conn = get_conn(MY_DB_URL)
            rows = fetch(conn, """
                SELECT payload FROM sensor_data_virtual
                WHERE payload::text LIKE '%%water-consumption%%'
                AND time >= %s
            """, [since])
            for row in rows:
                d = parse_payload(row)
                if "water-consumption" in d:
                    house_a_vals.append(float(d["water-consumption"]) * L_TO_GAL)
            conn.close()
        except Exception as e:
            traceback.print_exc()
            print(f"[A water error] {e}")
 
        # House B post-sharing — from my DB
        try:
            conn = get_conn(MY_DB_URL)
            rows = fetch(conn, """
                SELECT payload FROM sensor_data_virtual
                WHERE payload->>'board_name' = 'HouseB_Dishwasher_Board'
                AND time >= %s
            """, [since])
            for row in rows:
                d = parse_payload(row)
                if "HouseB_Dishwasher_Board_Sensor" in d:
                    house_b_vals.append(float(d["HouseB_Dishwasher_Board_Sensor"]) * L_TO_GAL)
            conn.close()
        except Exception as e:
            traceback.print_exc()
            print(f"[B water post-sharing error] {e}")
 
        # House B pre-sharing — fetch historical gap from Jack's DB
        if since < SHARING_START_UTC:
            try:
                conn = get_conn(JACK_DB_URL)
                rows = fetch(conn, """
                    SELECT payload FROM "IoT_Data_virtual"
                    WHERE payload->>'board_name' = 'HouseB_Dishwasher_Board'
                    AND time >= %s AND time < %s
                """, [since, SHARING_START_UTC])
                pre_count = 0
                for row in rows:
                    d = parse_payload(row)
                    if "HouseB_Dishwasher_Board_Sensor" in d:
                        house_b_vals.append(float(d["HouseB_Dishwasher_Board_Sensor"]) * L_TO_GAL)
                        pre_count += 1
                conn.close()
                completeness = f"COMPLETE (fetched {pre_count} pre-sharing records from House B DB)"
            except Exception as e:
                traceback.print_exc()
                completeness = f"PARTIAL — pre-sharing fetch failed: {e}"
        else:
            completeness = "COMPLETE (within sharing window)"
 
        all_vals = house_a_vals + house_b_vals
        if all_vals:
            avg = sum(all_vals) / len(all_vals)
            avg_a = sum(house_a_vals)/len(house_a_vals) if house_a_vals else 0
            avg_b = sum(house_b_vals)/len(house_b_vals) if house_b_vals else 0
            results.append(
                f"  {label}:\n"
                f"    Combined Avg: {avg:.4f} gal/cycle\n"
                f"    {HOUSE_A}: {avg_a:.4f} gal/cycle ({len(house_a_vals)} cycles)\n"
                f"    {HOUSE_B}: {avg_b:.4f} gal/cycle ({len(house_b_vals)} cycles)\n"
                f"    Status: {completeness}"
            )
        else:
            results.append(f"  {label}: No data available")
 
    return "=== Average Water Consumption per Cycle (Dishwashers) ===\n" + "\n".join(results.to_list())
 
def query_electricity():
    now = now_utc()
    since = now - timedelta(hours=24)
    house_a_watts = []
    house_b_watts = []
 
    # House A — from my DB
    try:
        conn = get_conn(MY_DB_URL)
        rows = fetch(conn, """
            SELECT payload FROM sensor_data_virtual
            WHERE payload::text LIKE '%%electric%%'
            AND payload::text LIKE '%%davidd.card05%%'
            AND time >= %s
        """, [since])
        for row in rows:
            d = parse_payload(row)
            for key in d:
                if "electric" in key.lower():
                    try:
                        house_a_watts.append(float(d[key]))
                    except:
                        pass
        conn.close()
    except Exception as e:
        traceback.print_exc()
        print(f"[A electricity error] {e}")
 
    # House B post-sharing — from my DB
    try:
        conn = get_conn(MY_DB_URL)
        rows = fetch(conn, """
            SELECT payload FROM sensor_data_virtual
            WHERE payload->>'board_name' = 'HouseB_Electricty_Meter_Board'
            AND time >= %s
        """, [since])
        for row in rows:
            d = parse_payload(row)
            if "HouseB_Electricty_Meter_Board_Sensor" in d:
                try:
                    house_b_watts.append(float(d["HouseB_Electricty_Meter_Board_Sensor"]))
                except:
                    pass
        conn.close()
    except Exception as e:
        traceback.print_exc()
        print(f"[B electricity post-sharing error] {e}")
 
    # House B pre-sharing — fetch historical gap from Jack's DB
    if since < SHARING_START_UTC:
        try:
            conn = get_conn(JACK_DB_URL)
            rows = fetch(conn, """
                SELECT payload FROM "IoT_Data_virtual"
                WHERE payload->>'board_name' = 'HouseB_Electricty_Meter_Board'
                AND time >= %s AND time < %s
            """, [since, SHARING_START_UTC])
            for row in rows:
                d = parse_payload(row)
                if "HouseB_Electricty_Meter_Board_Sensor" in d:
                    try:
                        house_b_watts.append(float(d["HouseB_Electricty_Meter_Board_Sensor"]))
                    except:
                        pass
            conn.close()
        except Exception as e:
            traceback.print_exc()
            print(f"[B electricity pre-sharing error] {e}")
 
    kwh_a = (sum(house_a_watts)/len(house_a_watts)*24/1000) if house_a_watts else 0
    kwh_b = (sum(house_b_watts)/len(house_b_watts)*24/1000) if house_b_watts else 0
    avg_a = (sum(house_a_watts)/len(house_a_watts)) if house_a_watts else 0
    avg_b = (sum(house_b_watts)/len(house_b_watts)) if house_b_watts else 0
    diff = abs(kwh_a - kwh_b)
 
    lines = LinkedList()
    lines.append(f"  {HOUSE_A}: {kwh_a:.4f} kWh (avg {avg_a:.2f}W, {len(house_a_watts)} readings)")
    lines.append(f"  {HOUSE_B}: {kwh_b:.4f} kWh (avg {avg_b:.2f}W, {len(house_b_watts)} readings)")
 
    if kwh_a == 0 and kwh_b == 0:
        lines.append("  No electricity data available yet.")
    elif kwh_a > kwh_b:
        lines.append(f"  Result: {HOUSE_A} consumed MORE by {diff:.4f} kWh")
        lines.append("  Analysis: House A shows higher power consumption over the past 24 hours.")
    elif kwh_b > kwh_a:
        lines.append(f"  Result: {HOUSE_B} consumed MORE by {diff:.4f} kWh")
        lines.append("  Analysis: House B shows higher power consumption over the past 24 hours.")
    else:
        lines.append("  Result: Both houses consumed equal electricity.")
 
    lines.append(f"  Sharing started: {to_pdt(SHARING_START_UTC)}")
    lines.append(f"  Query time: {to_pdt(now)}")
 
    return "=== Electricity Comparison (Past 24 Hours) ===\n" + "\n".join(lines.to_list())
 
def process_query(query):
    q = query.lower()
    if "moisture" in q:
        return query_moisture()
    elif "water consumption" in q:
        return query_water()
    elif "electricity" in q:
        return query_electricity()
    return "Unknown query."
 
def main():
    HOST = '0.0.0.0'
    PORT = 5000
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"[SERVER] Listening on port {PORT}...")
 
    while True:
        conn, addr = server.accept()
        print(f"[SERVER] Connected by {addr}")
        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                query = data.decode().strip()
                print(f"[SERVER] Query: {query}")
                result = process_query(query)
                conn.send(result.encode())
        except Exception as e:
            traceback.print_exc()
            print(f"[SERVER] Error: {e}")
        finally:
            conn.close()
 
if __name__ == "__main__":
    main()
 