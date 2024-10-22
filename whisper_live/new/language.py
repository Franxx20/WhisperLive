supported = [
	"en-US",
]


class Language:
    selected_language: str

    def __init__(self):
        self.selected_language = supported[0]
