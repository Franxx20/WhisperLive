supported = [
    {
        "name": "ulaw",
        "sampleRate": 8000,
        "attributes": [],
    },
    {
        "name": "slin16",
        "sampleRate": 16000,
        "attributes": [],
    },
    {
        "name": "opus",
        "sampleRate": 48000,
        "attributes": [],
    },
]


class Codec:
    selected_codec: dict

    def __init__(self):
        self.selected_codec = supported[0]
