
import asyncio
import ipaddress


class Host:
    def __init__(self, ip):
        self.ip = ip
        self.files = {}  # To store files (key: filename, value: content)
        self.shell = Shell(self)  # Initialize Shell with the host instance

    def create_file(self, filename, content):
        """Create or modify a file on the host."""
        self.files[filename] = content
        return f"File '{filename}' created with content: {content}"

    def delete_file(self, filename):
        """Delete a file from the host."""
        if filename in self.files:
            del self.files[filename]
            return f"File '{filename}' deleted."
        return f"File '{filename}' not found."

    def list_files(self):
        """List all files on the host."""
        if not self.files:
            return "No files available."
        return "\n".join(f"{filename}: {content}" for filename, content in self.files.items())

class Shell:
    def __init__(self, host):
        self.host = host

    def execute_command(self, command):
        """Execute the given command and return the result."""
        if command.startswith('create '):
            _, filename, content = command.split(maxsplit=2)
            return self.host.create_file(filename, content)
        elif command.startswith('delete '):
            _, filename = command.split(maxsplit=1)
            return self.host.delete_file(filename)
        elif command.lower() == 'list':
            return self.host.list_files()
        else:
            return "Unknown command. Type 'help' for available commands."


class Net:
    def __init__(self, network):
        self.network = ipaddress.ip_network(network)
        self.hosts = {}  # Mapping of IPs to Host objects
        self.used_ips = set()  # Keep track of used IPs

    def get_unused_ip(self):
        """Find and return an unused IP address from the network."""
        for ip in self.network.hosts():
            if ip not in self.used_ips:
                self.used_ips.add(ip)
                return str(ip)
        return None  # No unused IPs available

    def create_host(self):
        """Create a new Host object on an unused IP."""
        unused_ip = self.get_unused_ip()
        if unused_ip:
            new_host = Host(unused_ip)
            self.hosts[unused_ip] = new_host
            return new_host
        else:
            return None  # No available IPs


class Player:
    def __init__(self, player_id):
        self.player_id = player_id
        self.ip = None
        self.host = None

    def connect(self, net):
        """Connect to the network and get an IP and Host."""
        if self.ip is None:
            self.host = net.create_host()
            self.ip = self.host.ip if self.host else None
            return f"Player {self.player_id} connected to IP {self.ip}"
        else:
            return f"Player {self.player_id} already connected to IP {self.ip}"

    def disconnect(self, net):
        """Disconnect the player and manage the host."""
        if self.host:
            net.used_ips.remove(ipaddress.IPv4Address(self.ip))
            del net.hosts[self.ip]


class TelnetServer:
    def __init__(self, net):
        self.net = net
        self.players = {}

    async def handle_client(self, reader, writer):
        player_id = len(self.players) + 1  # Assign an ID to the player
        player = Player(player_id)
        self.players[player_id] = player
        
        welcome_message = f"Welcome Player {player_id}!\n"
        welcome_message += "Type 'help' for available commands.\n"
        writer.write(welcome_message.encode())
        await writer.drain()
        
        player.connect(self.net)

        while True:
            data = await reader.readline()
            command = data.decode().strip()

            if command.lower() == 'exit':
                player.disconnect(self.net)
                writer.write(f"Player {player_id} disconnected from {player.ip}.\n".encode())
                await writer.drain()
                break
            elif command.lower() == 'ps':
                msg = ""
                for ip in self.net.used_ips:
                    msg += f"{ip}\n"
                writer.write(msg.encode())
                await writer.drain()
            elif command.lower() == 'help':
                help_message = (
                    "Available commands:\n"
                    "  create <filename> <content> - Create a file on your host.\n"
                    "  delete <filename> - Delete a file on your host.\n"
                    "  list - List all files on your host.\n"
                    "  exit - Disconnect from the server.\n"
                )
                writer.write(help_message.encode())
                await writer.drain()
            else:
                # Delegate command execution to the Shell
                response = player.host.shell.execute_command(command)
                writer.write(response.encode())
                await writer.drain()

        writer.close()
        await writer.wait_closed()


async def main():
    # Create a network with a class C CIDR
    game_network = Net('192.168.1.0/24')
    server = TelnetServer(game_network)

    server_socket = await asyncio.start_server(server.handle_client, '127.0.0.1', 8888)

    async with server_socket:
        print("Server started on 127.0.0.1:8888")
        await server_socket.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
