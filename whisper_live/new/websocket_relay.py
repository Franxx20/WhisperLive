import asyncio
import json
import uuid
import time

import websockets
import websocket
import logging
import threading

from audio_processing import decode_ulaw_to_pcm
from codec import Codec

logging.basicConfig(level=logging.INFO)

codec = Codec()


def handle_get_request(request, response):
    if not request.get('params'):
        print('Error missing request parameters')
        return

    params = {

    }

    for p in request.get('params'):
        if p == 'codec':
            params['codec'] = codec.selected_codec
        elif p == 'language':
            params['language'] = 'en-US'
        elif p == 'results':
            params['results'] = 'this is a result'
        else:
            print('unsupported parameter')

    response['params'] = params

def handle_setup(request, response):
    print('received setup')
    response['codecs'] = [codec.selected_codec]
    response['params'] = {}


def handle_set_request(request, response):
    global codec
    params = {}

    codecs = None
    if request.get('codecs'):
        codecs = codec.selected_codec,

    if codec:
        response['codecs'] = codecs

    if 'language' in request:
        params['language'] = 'en-US'
    else:
        print(f'Ignoring unsopported parameter')

    response['params'] = params


def handle_request(message: dict):
    handlers = {
        'setup': handle_setup,
        'set': handle_set_request,
        'get': handle_get_request,
    }

    response = {
        "response": message.get('request'),
        "id": message.get('id')
    }

    # if binary_data:
    #     result = {
    #         'request': 'set',
    #         'id': uuid.uuid4(),
    #         'results': ['hola'],
    #     }
    #     # response['results'] = ["hola"]
    #     binary_data = False
    #     return result
    #
    # else:
    #
    try:
        print(message)
        handlers[message['request']](message, response)
    except:
        print('error ocurred')

    return response


class WebSocketRelay:
    def __init__(self, ws_ast_host="127.0.0.1", ws_ast_port=2700, ws_whisper_url="ws://127.0.0.1:9090"):
        self.last_response_received = None
        self.server_backend = "faster_whisper"
        self.server_error = False
        self.waiting = False
        self.model = 'tiny.en'
        self.ws_ast_host = ws_ast_host
        self.ws_ast_port = ws_ast_port
        self.ws_whisper_url = ws_whisper_url
        self.ws_whisper = None
        self.client_connections = {}

        self.task = "transcribe"
        self.use_vad = False
        self.uid = str(uuid.uuid4())
        self.language = 'en'
        self.last_segment = None
        self.last_received_segment = None
        self.log_transcription = True
        self.last_client_id = None

    def handle_status_messages(self, message_data):
        """Handles server status messages."""
        status = message_data["status"]
        if status == "WAIT":
            self.waiting = True
            print(f"[INFO]: Server is full. Estimated wait time {round(message_data['message'])} minutes.")
        elif status == "ERROR":
            print(f"Message from Server: {message_data['message']}")
            self.server_error = True
        elif status == "WARNING":
            print(f"Message from Server: {message_data['message']}")

    def on_message_whisper(self, ws_whisper, message):
        """
              Callback function called when a message is received from the server.

              It updates various attributes of the client based on the received message, including
              recording status, language detection, and server messages. If a disconnect message
              is received, it sets the recording status to False.

              Args:
                  ws (websocket.WebSocketApp): The WebSocket client instance.
                  message (str): The received message from the server.

              """
        message = json.loads(message)
        print(message)
        print(self.uid)

        if "status" in message.keys():
            self.handle_status_messages(message)
            return

        if "message" in message.keys() and message["message"] == "DISCONNECT":
            print("[INFO]: Server disconnected due to overtime.")
            self.recording = False

        if "message" in message.keys() and message["message"] == "SERVER_READY":
            self.last_response_received = time.time()
            self.server_backend = message["backend"]
            print(f"[INFO]: Server Running with backend {self.server_backend}")
            return

        if "language" in message.keys():
            self.language = message.get("language")
            lang_prob = message.get("language_prob")
            print(
                f"[INFO]: Server detected language {self.language} with probability {lang_prob}"
            )

        client_id = getattr(self, 'last_client_id', None)
        if client_id is None or client_id not in self.client_connections:
            logging.error("Unable to find the original client to send the response")
            return

        client_websocket = self.client_connections[client_id]
        asyncio.run_coroutine_threadsafe(client_websocket.send(message), asyncio.get_event_loop())

        logging.info(f"Sent response back to client {client_id}")

    def on_open_whisper(self, ws_whisper):
        """
        Callback function called when the WebSocket connection is successfully opened.

        Sends an initial configuration message to the server, including client UID,
        language selection, and task type.

        Args:
            ws_whisper (websocket.WebSocketApp): The WebSocket client instance.

        """
        print("[INFO]: Opened connection")
        ws_whisper.send(
            json.dumps(
                {
                    "uid": str(uuid.uuid4()),
                    "language": self.language,
                    "task": self.task,
                    "model": self.model,
                    "use_vad": self.use_vad,
                }
            )
        )

    async def websocket_ast_handler(self, ws_ast, path):
        """Handle incoming connections and messages from WebSocket ast clients."""
        client_id = id(ws_ast)
        self.client_connections[client_id] = ws_ast

        logging.info(f"Client {client_id} connected to WebSocket ast")
        try:
            async for message in ws_ast:
                if isinstance(message, bytes):
                    logging.info(f"Received {len(message)} bytes from client {client_id}")

                    pcm_data = decode_ulaw_to_pcm(message)
                    self.ws_whisper.send(pcm_data, websocket.ABNF.OPCODE_BINARY)

                    self.last_client_id = client_id

                    logging.info(f"Sent response back to client {client_id}")
                else:
                    parsed_message = json.loads(message)
                    print(parsed_message)
                    if 'request' in parsed_message:
                        parsed_message = handle_request(parsed_message)
                    else:
                        parsed_message = None

                    print(f'handled: {parsed_message}')
                    if parsed_message:
                        parsed_message = json.dumps(parsed_message)
                        await ws_ast.send(parsed_message)
                        print('message sent')
        except websockets.exceptions.ConnectionClosed:
            logging.info(f"Client {client_id} disconnected")
        finally:
            del self.client_connections[client_id]

    def start_websocket_whisper(self):
        """Start the WebSocket whisper client."""
        self.ws_whisper = websocket.WebSocketApp(
            self.ws_whisper_url,
            on_message=lambda ws, message: self.on_message_whisper(ws, message),
            on_open=lambda ws: self.on_open_whisper(ws),
            on_error=lambda ws, err: logging.error(f"WebSocket whisper error: {err}"),
            on_close=lambda ws, code, msg: self.on_close(ws, code, msg)
        )
        self.ws_whisper.run_forever()

    def start_websocket_ast(self):
        """Start the WebSocket ast server."""
        server = websockets.serve(self.websocket_ast_handler, self.ws_ast_host, self.ws_ast_port)
        asyncio.get_event_loop().run_until_complete(server)
        logging.info(f"WebSocket ast server running on {self.ws_ast_host}:{self.ws_ast_port}")
        asyncio.get_event_loop().run_forever()

    def run(self):
        """Run the relay by starting both WebSocket ast server and WebSocket whisper client."""
        threading.Thread(target=self.start_websocket_whisper, daemon=True).start()
        self.start_websocket_ast()

    def on_close(self, ws, code, msg):
        print(f"[INFO]: Websocket connection closed: {code}: {msg}")
        self.waiting = False


if __name__ == "__main__":
    relay = WebSocketRelay(
        ws_ast_host="0.0.0.0",
        ws_ast_port=2700,
        ws_whisper_url="ws://127.0.0.1:9090"
    )
    try:
        relay.run()
    except KeyboardInterrupt:
        logging.info("WebSocket relay terminated by user")
