import time
import textwrap

class TranscriptBuffer:
    def __init__(self):
        self.buffer = []  # Store the last three results
        self.last_print_time = time.time()  # Keep track of the last time we printed
        self.timeout = 10  # Timeout to print if 10 seconds pass
        self.same_threshold = 3  # Number of same consecutive results to trigger print
        self.has_printed = False  # Flag to avoid double printing

    def print_transcript(self, text):
        """Prints formatted transcript text."""
        wrapper = textwrap.TextWrapper(width=60)
        for line in wrapper.wrap(text="".join(text)):
            print(line)

    def update_buffer(self, new_result):
        """
        Updates the transcript buffer and prints if certain conditions are met:
        - Print when the same result appears 3 times consecutively.
        - Print after 10 seconds have passed since the last print.
        """
        current_time = time.time()

        # Add new result to buffer, remove oldest if buffer exceeds 3 items
        self.buffer.append(new_result)
        if len(self.buffer) > 3:
            self.buffer.pop(0)

        # Check if we have 3 consecutive same results
        if len(set(self.buffer)) == 1 and len(self.buffer) == self.same_threshold and not self.has_printed:
            self.print_transcript(self.buffer[-1])  # Print the last result
            self.buffer.clear()  # Reset buffer after printing
            self.last_print_time = current_time  # Reset last print time
            self.has_printed = True  # Set the flag to prevent double printing

        # Check if 10 seconds have passed since the last print
        elif current_time - self.last_print_time > self.timeout:
            if self.buffer:  # Only print if buffer has content
                self.print_transcript(self.buffer[-1])
                self.buffer.clear()  # Reset buffer after printing
            self.last_print_time = current_time  # Update last print time
            self.has_printed = False  # Reset flag to allow next print on consecutive matches

#
# # Example usage
# buffer = TranscriptBuffer()
#
# # Simulate receiving new transcript results
# transcript_results = ["Hello world", "Hello world", "Hello world", "Hello GPT", "Hello GPT", "Hello GPT"]
#
# for result in transcript_results:
#     buffer.update_buffer(result)
#     time.sleep(1)  # Simulate a delay between results
