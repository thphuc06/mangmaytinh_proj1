class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.file = open(filename, 'rb')
		except:
			raise IOError
		self.frameNum = 0

		# Detect file format by checking first 5 bytes
		first_bytes = self.file.read(5)
		self.file.seek(0)  # Reset to beginning

		# Check if it's the custom format (ASCII frame length) or standard MJPEG
		try:
			int(first_bytes)  # If this works, it's custom format
			self.is_custom_format = True
		except ValueError:
			self.is_custom_format = False  # Standard MJPEG format

	def nextFrame(self):
		"""Get next frame."""
		if self.is_custom_format:
			# Custom format: 5 ASCII bytes for frame length, then frame data
			data = self.file.read(5) # Get the framelength from the first 5 bytes
			if data:
				framelength = int(data)

				# Read the current frame
				data = self.file.read(framelength)
			return data
		else:
			# Standard MJPEG format: Find JPEG markers (SOI: 0xFFD8, EOI: 0xFFD9)
			# Read in chunks for better performance
			chunk_size = 4096
			frame_data = bytearray()
			found_start = False

			while True:
				chunk = self.file.read(chunk_size)
				if not chunk:
					break

				if not found_start:
					# Look for start marker FF D8
					start_idx = chunk.find(b'\xff\xd8')
					if start_idx != -1:
						frame_data.extend(chunk[start_idx:])
						found_start = True
					continue

				# Look for end marker FF D9
				frame_data.extend(chunk)
				end_idx = bytes(frame_data).find(b'\xff\xd9')

				if end_idx != -1:
					# Found complete frame
					# Calculate how much we over-read and seek back
					total_len = len(frame_data)
					frame_len = end_idx + 2
					over_read = total_len - frame_len

					if over_read > 0:
						self.file.seek(-over_read, 1)

					# Keep only the frame data (up to end marker inclusive)
					return bytes(frame_data[:frame_len])

			return bytes(frame_data) if found_start else b''

	# def frameNbr(self):
	# 	"""Get frame number."""
	# 	return self.frameNum

