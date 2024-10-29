import asyncio
import json
import uuid
import time

import numpy as np
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

    try:
        print(message)
        handlers[message['request']](message, response)
    except:
        print('error ocurred')

    return response


class WebSocketRelay:
    def __init__(self, ws_ast_host="127.0.0.1", ws_ast_port=2700, ws_whisper_url="ws://127.0.0.1:9090"):
        self.last_client_id = None
        self.server_backend = "faster_whisper"
        self.server_error = False
        self.waiting = False
        self.model = 'tiny.en'
        self.ws_ast_host = ws_ast_host
        self.ws_ast_port = ws_ast_port
        self.ws_whisper_url = ws_whisper_url
        self.client_connections = {}
        self.language = 'en'

        self.whisper_event_loop = None
        self.ws_whisper = None

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

    async def send_to_client(self, client_id, message):
        """Send a message back to the AST client."""
        client_websocket = self.client_connections.get(client_id)
        # message_json = json.dumps(message)
        results = {
            [message.get('segments')[0].get('text')]
        }
        request = {
            'request': "set",
            'id': f"{uuid.uuid4()}",
            'results': results,
        }
        if client_websocket:
            await client_websocket.send(json.dumps(request))

    def on_message_whisper(self, ws_whisper, message):
        """
        Callback for handling messages from the Whisper WebSocket.
        """
        message = json.loads(message)
        print(f"Response from Whisper: {message}")

        if "status" in message.keys():
            self.handle_status_messages(message)
            return

        if "message" in message.keys() and message["message"] == "DISCONNECT":
            print("[INFO]: Server disconnected due to overtime.")

        if "message" in message.keys() and message["message"] == "SERVER_READY":
            self.server_backend = message["backend"]
            print(f"[INFO]: Server Running with backend {self.server_backend}")
            return

        if "language" in message.keys():
            self.language = message.get("language")
            lang_prob = message.get("language_prob")
            print(
                f"[INFO]: Server detected language {self.language} with probability {lang_prob}"
            )

        client_id = self.last_client_id
        if client_id is None or client_id not in self.client_connections:
            logging.error("Unable to find the original client to send the response")
            return

        asyncio.run_coroutine_threadsafe(self.send_to_client(client_id, message), asyncio.get_event_loop())

    def on_open_whisper(self, ws_whisper):
        """
        Called when the Whisper WebSocket connection is opened.
        """
        print("[INFO]: Opened Whisper WebSocket connection")
        ws_whisper.send(json.dumps({
            "uid": str(uuid.uuid4()),
            "language": self.language,
            "task": "transcribe",
            "model": self.model,
            "use_vad": True,
        }))

    async def websocket_ast_handler(self, ws_ast, path):
        """Handle AST WebSocket connections."""
        client_id = id(ws_ast)
        self.client_connections[client_id] = ws_ast

        logging.info(f"Client {client_id} connected")
        try:
            async for message in ws_ast:
                if isinstance(message, bytes):
                    pcm_data = decode_ulaw_to_pcm(message)
                    audio_array = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0

                    # Send audio data to Whisper
                    self.ws_whisper.send(audio_array.tobytes(), websocket.ABNF.OPCODE_BINARY)

                    self.last_client_id = client_id
                else:
                    parsed_message = json.loads(message)
                    response = handle_request(parsed_message)
                    if response:
                        await ws_ast.send(json.dumps(response))
        except websockets.exceptions.ConnectionClosed:
            logging.info(f"Client {client_id} disconnected")
        finally:
            del self.client_connections[client_id]

    def start_whisper_loop(self):
        """Start the WebSocket Whisper client in a separate event loop."""
        self.whisper_event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.whisper_event_loop)
        self.ws_whisper = websocket.WebSocketApp(
            self.ws_whisper_url,
            on_message=self.on_message_whisper,
            on_open=self.on_open_whisper,
            on_error=lambda ws, err: logging.error(f"WebSocket Whisper error: {err}"),
            on_close=lambda ws, code, msg: logging.info(f"Whisper WebSocket closed: {code}, {msg}")
        )
        self.ws_whisper.run_forever()

    def start_websocket_ast(self):
        """Start the WebSocket AST server."""
        asyncio.get_event_loop().run_until_complete(
            websockets.serve(self.websocket_ast_handler, self.ws_ast_host, self.ws_ast_port))
        logging.info(f"WebSocket AST server running on {self.ws_ast_host}:{self.ws_ast_port}")
        asyncio.get_event_loop().run_forever()

    def run(self):
        """Run both the AST server and Whisper client in separate threads."""
        whisper_thread = threading.Thread(target=self.start_whisper_loop, daemon=True)
        whisper_thread.start()

        # Run the AST WebSocket server
        self.start_websocket_ast()


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
