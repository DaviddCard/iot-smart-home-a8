import socket
 
SERVER_IP = '127.0.0.1'
PORT = 5000
 
VALID_QUERIES = {
    "1": "What is the average moisture inside our kitchen fridges in the past hours, week and month?",
    "2": "What is the average water consumption per cycle across our smart dishwashers in the past hour, week and month?",
    "3": "Which house consumed more electricity in the past 24 hours, and by how much?"
}
 
def print_menu():
    print("\n=== IoT Smart Home Query System ===")
    print("Supported queries:")
    for num, query in VALID_QUERIES.items():
        print(f"  {num}. {query}")
    print("  q. Quit")
    print("====================================\n")
 
def main():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((SERVER_IP, PORT))
        print(f"Connected to server at {SERVER_IP}:{PORT}")
    except ConnectionRefusedError:
        print("Could not connect to server. Make sure server.py is running.")
        return
 
    print_menu()
 
    while True:
        try:
            user_input = input("Enter query number (1/2/3) or type your query: ").strip()
        except KeyboardInterrupt:
            print("\nDisconnecting...")
            break
 
        if user_input.lower() == 'q':
            print("Disconnecting...")
            break
 
        # Allow selecting by number or typing the full query
        if user_input in VALID_QUERIES:
            query = VALID_QUERIES[user_input]
        elif user_input in VALID_QUERIES.values():
            query = user_input
        else:
            print("\nSorry, this query cannot be processed. Please try one of the supported queries.\n")
            print_menu()
            continue
 
        print(f"\nSending: {query}")
        client.send(query.encode())
 
        response = client.recv(8192).decode()
        print(f"\n{response}\n")
 
    client.close()
 
if __name__ == "__main__":
    main()