import socket
import os
from pathlib import Path

HEADER = 512
FORMAT = 'utf-8'

IP_ADDRESS = "127.0.0.1"
PERMANENT_PORT = 12345  

#Creates UDP Socket
def create_socket():
    return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def display_commands():
    print("COMMAND LISTS")
    print("/join <server_ip_add> <port>")
    print("/leave")
    print("/register <handle>")
    print("/store <filename>")
    print("/dir")
    print("/get <filename>")

def send_to_server(client, msg):
    try:
        message = msg
        if isinstance(msg,bytes) == False:
            message = msg.encode(FORMAT)
        msg_length = len(message)
        send_length = str(msg_length).encode(FORMAT)
        send_length += b' ' * (HEADER - len(send_length))
        client.send(send_length)
        client.send(message)

        return client.recv(HEADER).decode(FORMAT)
    except (ConnectionResetError, ConnectionAbortedError, socket.error) as e:
        print(f"Error: Server connection lost. {e}")
        return None


def main():
    is_server_active = False
    is_user_registered = False
    client = create_socket()  # Create the socket initially

    input_server = ""
    input_port = -1


    os.chdir(r"C:\Users\perez\OneDrive\Desktop\CSNETWK_MachineProject-main") # change before running 

    from_path = Path.cwd() / "CSNETWORK_MP" / "Client Directory"
    if not from_path.exists():
        print(f"Error: Directory does not exist: {from_path}")
        return

    from_files = list(from_path.glob("*"))  # List all files and directories
    from_file_names = [f.name for f in from_files if f.is_file()]  # Only include file names

    try:
        while True:
            server_response = ""

            prompt = input("> ").strip()
            if not prompt:
                print("Error: No command entered. Please try again.")
                continue  # Skip this iteration and go back to prompting the user
            cmd_key = prompt.split()

            if cmd_key[0] == "/join":
                if len(cmd_key) == 3:
                    input_server = cmd_key[1]  # a string
                    input_port = int(cmd_key[2])  # an int
                    address = (input_server, input_port)

                if input_port == PERMANENT_PORT and input_server == IP_ADDRESS and len(cmd_key) == 3 and is_server_active == False:
                    is_server_active = True
                    client.connect(address)
                    server_response = send_to_server(client, prompt)
                    print(server_response)
                elif input_port == PERMANENT_PORT and input_server == IP_ADDRESS and len(cmd_key) == 3 and is_server_active == True:
                    print("Error: Connection to the Server is already active.")
                elif (input_port != PERMANENT_PORT or input_server != IP_ADDRESS) and len(cmd_key) == 3:
                    print("Error: Connection to the Server has failed! Please check IP Address and Port Number.")
                else:
                    print("Error: Command parameters do not match or are not allowed.")

            elif cmd_key[0] == "/leave":
                if is_server_active:
                    server_response = send_to_server(client, prompt)
                    if server_response is None:  # Server is unreachable
                        print("Error: Server connection lost.")
                    else:
                        print(server_response)
                        if server_response == "Connection closed. Thank you!":
                            is_user_registered = False
                            is_server_active = False
                    client.close()  # Close the socket
                    client = create_socket()  # Recreate the socket for future use
                else:
                    print("Error: Disconnection failed. Please connect to the server first.")

            elif cmd_key[0] == "/store":
                if is_server_active:
                    if is_user_registered:
                        if len(cmd_key) == 2:  # Assuming /store requires one parameter
                            file_name = cmd_key[1]
                            file_path = from_path / file_name

                            if file_name not in from_file_names:
                                print("Error: File not found.")
                            else:

                                try:
                                    # Open and read the file content
                                    with open(file_path, "rb") as file:
                                        data = file.read()

                                    # Create the message to send (filename + file data)
                                    prompt = prompt.encode(FORMAT)
                                    prompt = prompt + b" " + data
                                    
                                    server_response = send_to_server(client, prompt)  # Send the full data (filename + content)

                                    if server_response is None:  # Server is unreachable
                                        is_server_active = False
                                        client.close()  # Close the socket
                                        client = create_socket()  # Recreate the socket for future use
                                        print("Error: Server connection lost.")
                                    else:
                                        print(server_response)
                                    file.close()
                                except FileNotFoundError:
                                    print(f"Error: The file {file_name} was not found.")
                                except Exception as e:
                                    print(f"Error while reading the file: {e}")
                        else:
                            print("Error: Command parameters do not match or are not allowed.")
                    else:
                        print("Error: User is not yet registered.")
                else:
                    print("Error: Please connect to the server first to use this command.")

            elif cmd_key[0] == "/dir":
                if is_server_active:
                    if is_user_registered:
                        server_response = send_to_server(client, prompt)
                        if server_response is None:  # Server is unreachable
                            is_server_active = False
                            client.close()  # Close the socket
                            client = create_socket()  # Recreate the socket for future use
                            print("Error: Server connection lost.")
                        else:
                            print(server_response)
                    else:
                        print("Error: User is not yet registered.")
                else:
                    print("Error: Please connect to the server first to use this command.")

            elif cmd_key[0] == "/get":
                if is_server_active:
                    if is_user_registered:
                        if len(cmd_key) == 2:  # Assuming /get requires one parameter
                            server_response = send_to_server(client, prompt)
                            if server_response is None:  # Server is unreachable
                                is_server_active = False
                                client.close()  # Close the socket
                                client = create_socket()  # Recreate the socket for future use
                                print("Error: Server connection lost.")
                            elif server_response == "Error: File not found in the server.":
                                print(server_response)
                            else:
                                #print(server_response)
                                data = client.recv(HEADER).decode(FORMAT)
                                print(data)

                                file_path = from_path / cmd_key[1]
                                cmd_key[1], file_extension = os.path.splitext(cmd_key[1])

                                try:
                                    if file_extension == ".txt":
                                        with open(file_path, "w") as file:
                                            file.write(data)
                                    else:
                                        data = data.encode(FORMAT)
                                        with open(file_path, "wb") as file:
                                            file.write(data)
                                except Exception as e:
                                    print(f"Error: {e}.")
                        else:
                            print("Error: Command parameters do not match or are not allowed.")
                    else:
                        print("Error: User is not yet registered.")
                else:
                    print("Error: Please connect to the server first to use this command.")

            elif cmd_key[0] == "/register":
                if len(cmd_key) != 2:
                    print("Error: Command parameters do not match or are not allowed.")
                elif is_server_active:
                    server_response = send_to_server(client, prompt)
                    temp = server_response.split()
                    if len(temp) == 2:
                        is_user_registered = True
                    print(server_response)
                else:
                    print("Error: Please connect to the server first to use this command.")

            elif cmd_key[0] == "ayaw kona":
                break

            elif cmd_key[0] == "/?":
                display_commands()
                
            else:
                print("Error: Command not found.")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

print("\nCLIENT INTERFACE")
print("> CLIENT HAS STARTED")
main()


