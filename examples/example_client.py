import os
import time
import subprocess

from whisper_live.client import TranscriptionClient

last_text = ""

def sample_callback(text, is_final):
  global last_text
  global client

  if is_final and text != last_text:
    last_text = text
    client.paused = True
    print(f'final word is: {text[-1]}',flush=True)

    client.paused = False
  else:
    os.system("cls" if os.name == "nt" else "clear")
    # print(text[-1], end='', flush=True)

client = TranscriptionClient(
  "localhost",
  9090,
  lang="en",
  translate=False,
  model="tiny.en",
  use_vad=True,
  callback=sample_callback
)

client()
