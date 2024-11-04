import audioop


def decode_ulaw_to_pcm(ulaw_data: bytes):
    return audioop.ulaw2lin(ulaw_data, 2)
