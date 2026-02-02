"""SSDP (Simple Service Discovery Protocol) server for HDHomeRun device discovery"""

import builtins
import contextlib
import logging
import platform
import socket
import threading

from ..config import get_config

logger = logging.getLogger(__name__)


class SSDPServer:
    """SSDP server for HDHomeRun device discovery"""

    SSDP_MULTICAST_IP = "239.255.255.250"
    SSDP_PORT = 1900
    HDHOMERUN_ST = "urn:schemas-upnp-org:device:MediaServer:1"

    def __init__(self, device_id: str = "FFFFFFFF", friendly_name: str = "EXStreamTV HDHomeRun"):
        self.device_id = device_id
        self.friendly_name = friendly_name
        self.running = False
        self.socket: socket.socket | None = None
        self.thread: threading.Thread | None = None

        # Get server info from config
        config = get_config()
        self.server_host = config.server.host
        self.server_port = config.server.port
        self.base_url = config.server.base_url

        # HDHomeRun typically uses port 5004, but we'll use our main port
        self.hdhomerun_port = self.server_port

    def _get_location_url(self) -> str:
        """Get the location URL for device description"""
        # Use the base URL from config, or construct from host/port
        if self.base_url and self.base_url != "http://localhost:8411":
            return f"{self.base_url}/hdhomerun/device.xml"
        else:
            host = self.server_host if self.server_host != "0.0.0.0" else "127.0.0.1"
            return f"http://{host}:{self.server_port}/hdhomerun/device.xml"

    def _create_ssdp_response(self, request_type: str) -> bytes:
        """Create SSDP response message"""
        location = self._get_location_url()

        response = (
            "HTTP/1.1 200 OK\r\n"
            f"ST: {self.HDHOMERUN_ST}\r\n"
            f"USN: uuid:{self.device_id}::{self.HDHOMERUN_ST}\r\n"
            f"Location: {location}\r\n"
            f"Cache-Control: max-age=1800\r\n"
            f"Server: EXStreamTV/1.0 UPnP/1.0\r\n"
            f"EXT:\r\n"
            "\r\n"
        )
        return response.encode("utf-8")

    def _create_notify_message(self) -> bytes:
        """Create SSDP NOTIFY message"""
        location = self._get_location_url()

        notify = (
            "NOTIFY * HTTP/1.1\r\n"
            f"HOST: {self.SSDP_MULTICAST_IP}:{self.SSDP_PORT}\r\n"
            f"NT: {self.HDHOMERUN_ST}\r\n"
            f"NTS: ssdp:alive\r\n"
            f"USN: uuid:{self.device_id}::{self.HDHOMERUN_ST}\r\n"
            f"Location: {location}\r\n"
            f"Cache-Control: max-age=1800\r\n"
            f"Server: EXStreamTV/1.0 UPnP/1.0\r\n"
            "\r\n"
        )
        return notify.encode("utf-8")

    def _handle_ssdp_request(self, data: bytes, addr: tuple):
        """Handle incoming SSDP request"""
        try:
            request = data.decode("utf-8", errors="ignore")

            # Check if it's an M-SEARCH request
            if "M-SEARCH" in request:
                # Check if it's looking for our device type
                if self.HDHOMERUN_ST in request or "ssdp:all" in request:
                    logger.debug(f"SSDP M-SEARCH request from {addr}")
                    response = self._create_ssdp_response("M-SEARCH")
                    self.socket.sendto(response, addr)
                    logger.debug(f"Sent SSDP response to {addr}")
        except Exception as e:
            logger.exception(f"Error handling SSDP request: {e}")

    def _send_notify(self):
        """Send SSDP NOTIFY message"""
        try:
            notify_msg = self._create_notify_message()
            addr = (self.SSDP_MULTICAST_IP, self.SSDP_PORT)
            self.socket.sendto(notify_msg, addr)
            logger.debug("Sent SSDP NOTIFY message")
        except Exception as e:
            logger.exception(f"Error sending SSDP NOTIFY: {e}")

    def _run(self):
        """Main SSDP server loop"""
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Try to set SO_REUSEPORT if available (allows port sharing on Linux/macOS)
            # This allows multiple processes to bind to the same port for multicast
            try:
                if platform.system() in ["Darwin", "Linux"]:
                    # macOS uses 0x0200, Linux uses 15, but both might be available via socket constant
                    # Try the socket constant first (if available)
                    if hasattr(socket, "SO_REUSEPORT"):
                        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                        logger.debug("SO_REUSEPORT enabled for port sharing")
                    else:
                        # Try macOS value (0x0200)
                        try:
                            SO_REUSEPORT = 0x0200
                            self.socket.setsockopt(socket.SOL_SOCKET, SO_REUSEPORT, 1)
                            logger.debug("SO_REUSEPORT enabled for port sharing (macOS)")
                        except (AttributeError, OSError):
                            # Try Linux value (15)
                            try:
                                SO_REUSEPORT = 15
                                self.socket.setsockopt(socket.SOL_SOCKET, SO_REUSEPORT, 1)
                                logger.debug("SO_REUSEPORT enabled for port sharing (Linux)")
                            except (AttributeError, OSError):
                                logger.debug("SO_REUSEPORT not available on this platform")
            except Exception as e:
                logger.debug(f"Could not set SO_REUSEPORT: {e}")

            # Bind to all interfaces
            try:
                self.socket.bind(("", self.SSDP_PORT))
                logger.debug(f"Successfully bound to port {self.SSDP_PORT}")
            except OSError as e:
                if e.errno == 48:  # Address already in use
                    # Try binding to a specific interface instead
                    try:
                        # Try binding to localhost only as fallback
                        self.socket.bind(("127.0.0.1", self.SSDP_PORT))
                        logger.warning(
                            f"SSDP port {self.SSDP_PORT} was in use, bound to localhost only."
                        )
                        logger.warning("SSDP discovery may be limited to local network.")
                    except OSError:
                        logger.warning(
                            f"SSDP port {self.SSDP_PORT} is already in use and cannot be shared."
                        )
                        logger.warning("SSDP discovery will be disabled.")
                        logger.warning(
                            "HDHomeRun device can still be added manually using the discover.json URL."
                        )
                        logger.info("To enable SSDP, you can:")
                        logger.info("  1. Stop other applications using port 1900 (like Plex)")
                        logger.info("  2. Set enable_ssdp: false in config.yaml to disable SSDP")
                        return
                else:
                    raise

            # Join multicast group
            try:
                mreq = socket.inet_aton(self.SSDP_MULTICAST_IP) + socket.inet_aton("0.0.0.0")
                self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            except OSError as e:
                logger.warning(f"Could not join SSDP multicast group: {e}")
                logger.warning("SSDP discovery may not work correctly.")

            # Set socket timeout for periodic NOTIFY messages
            self.socket.settimeout(30.0)

            logger.info(f"SSDP server started on port {self.SSDP_PORT}")

            # Send initial NOTIFY
            self._send_notify()

            # Send periodic NOTIFY messages
            notify_count = 0
            while self.running:
                try:
                    data, addr = self.socket.recvfrom(1024)
                    self._handle_ssdp_request(data, addr)
                except TimeoutError:
                    # Send periodic NOTIFY every 30 seconds
                    notify_count += 1
                    if notify_count >= 2:  # Every 60 seconds
                        self._send_notify()
                        notify_count = 0
                except Exception as e:
                    if self.running:
                        logger.exception(f"Error in SSDP server loop: {e}")
        except Exception as e:
            logger.exception(f"SSDP server error: {e}")
            logger.info(
                "HDHomeRun device can still be accessed manually at /hdhomerun/discover.json"
            )
        finally:
            if self.socket:
                try:
                    # Leave multicast group before closing
                    try:
                        mreq = socket.inet_aton(self.SSDP_MULTICAST_IP) + socket.inet_aton(
                            "0.0.0.0"
                        )
                        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
                    except (OSError, socket.error):
                        pass
                    self.socket.close()
                except (OSError, socket.error):
                    pass
            logger.info("SSDP server stopped")

    def start(self):
        """Start the SSDP server"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("SSDP server starting...")

    def stop(self):
        """Stop the SSDP server"""
        if not self.running:
            return

        self.running = False
        if self.socket:
            with contextlib.suppress(builtins.BaseException):
                self.socket.close()

        if self.thread:
            self.thread.join(timeout=2)

        logger.info("SSDP server stopped")
