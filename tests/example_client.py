from whisper_live.client import TranscriptionClient
import os
import time
import subprocess

import whisper_live.utils
last_text = ""

def sample_callback(text, is_final):
  global last_text
  global client

  if is_final and text != last_text:
    # print("\r" + text[-1], end='', flush=True)
    last_text = text
    client.paused = True
    # Define the command to be run
    # command = f'echo "{text[-1]}" | piper --model en_US-lessac-medium --output-raw | aplay -r 22050 -f S16_LE -t raw -'
    # Run the command
    # subprocess.run(command, shell=True, check=True)
    print(f'TEXTO FINAL DE LA TRANSCRIPCION: {text[-1]}')

    client.paused = False
  else:
    os.system("cls" if os.name == "nt" else "clear")
    # print(text[-1], end='', flush=True)
    whisper_live.utils.print_transcript(text)
  print(is_final)

def transcription_callback(text,is_final):
  print(f'transcripcion {text}')

client = TranscriptionClient(
  "localhost",
  9090,
  lang="en",
  translate=False,
  model="tiny.en",
  use_vad=True,
  callback=transcription_callback()
)

client()
