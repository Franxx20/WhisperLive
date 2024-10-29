import torch
torch.set_num_threads(1)

model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad')
(get_speech_timestamps, _, read_audio, _, _) = utils

# wav = read_audio('/home/pilum/development/sirius/mass-nexus/sounds/en/en_US/amy/medium/inbound_1.wav')
wav = read_audio('/home/pilum/Documents/record.mp3')
speech_timestamps = get_speech_timestamps(
  wav,
  model,
  return_seconds=True,  # Return speech timestamps in seconds (default is samples)
)
print(speech_timestamps)