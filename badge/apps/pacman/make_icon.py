#!/usr/bin/env python3
import struct
import zlib

def create_png(width, height, pixels):
    """Create a simple PNG file from RGB pixel data"""

    def png_chunk(chunk_type, data):
        chunk_data = chunk_type + data
        crc = zlib.crc32(chunk_data) & 0xffffffff
        return struct.pack(">I", len(data)) + chunk_data + struct.pack(">I", crc)

    # PNG signature
    png_signature = b'\x89PNG\r\n\x1a\n'

    # IHDR chunk
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = png_chunk(b'IHDR', ihdr_data)

    # IDAT chunk - image data
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # filter type
        for x in range(width):
            r, g, b = pixels[y][x]
            raw_data += struct.pack("BBB", r, g, b)

    compressed_data = zlib.compress(raw_data, 9)
    idat_chunk = png_chunk(b'IDAT', compressed_data)

    # IEND chunk
    iend_chunk = png_chunk(b'IEND', b'')

    return png_signature + ihdr_chunk + idat_chunk + iend_chunk

# Create 24x24 pixel array for pacman icon
width, height = 24, 24
pixels = [[(0, 0, 0) for _ in range(width)] for _ in range(height)]

# Draw Pac-Man (yellow circle with mouth)
cx, cy = 12, 12
radius = 9

for y in range(height):
    for x in range(width):
        dx = x - cx
        dy = y - cy
        dist = (dx * dx + dy * dy) ** 0.5

        # Draw circle
        if dist <= radius:
            # Create mouth opening (wedge on right side)
            angle_from_center = 0
            if dx != 0 or dy != 0:
                import math
                angle_from_center = math.atan2(dy, dx)
                angle_deg = math.degrees(angle_from_center)
                # Normalize to 0-360
                if angle_deg < 0:
                    angle_deg += 360

                # Mouth opening from -30 to +30 degrees (facing right)
                if angle_deg < 30 or angle_deg > 330:
                    continue  # Skip pixels in mouth area

            pixels[y][x] = (255, 255, 0)  # Yellow

# Draw a couple of dots in front of pac-man
pixels[12][20] = (255, 255, 255)
pixels[12][22] = (255, 255, 255)

# Create and save PNG
png_data = create_png(width, height, pixels)
with open('icon.png', 'wb') as f:
    f.write(png_data)

print("Pac-Man icon created successfully!")
