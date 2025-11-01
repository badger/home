"""
jpegdec.py
==========

Stub implementation of jpegdec for the badge simulator.
Provides JPEG decoding capability using Pygame/PIL.
"""

import os
try:
    import pygame
except ImportError:
    raise SystemExit("Pygame is required for jpegdec simulator")


class JPEG:
    """JPEG decoder that works with badge simulator screens."""
    
    def __init__(self, display):
        """
        Initialize JPEG decoder.
        
        Args:
            display: The screen/display surface to decode images onto
        """
        self.display = display
        self._surface = None
        self._width = 0
        self._height = 0
    
    def open_file(self, filename):
        """
        Open a JPEG file for decoding.
        
        Args:
            filename: Path to the JPEG file
        """
        # Map system paths if needed
        if hasattr(self.display, '_surface'):
            # It's a badgeware screen, might need path mapping
            from badge_simulator import map_system_path
            filename = map_system_path(filename)
        
        try:
            self._surface = pygame.image.load(filename).convert_alpha()
            self._width = self._surface.get_width()
            self._height = self._surface.get_height()
        except Exception as e:
            raise OSError(f"Failed to open JPEG file '{filename}': {e}")
    
    def get_width(self):
        """Get the width of the opened JPEG image."""
        if self._surface is None:
            return 0
        return self._width
    
    def get_height(self):
        """Get the height of the opened JPEG image."""
        if self._surface is None:
            return 0
        return self._height
    
    def decode(self, x, y, scale=1):
        """
        Decode the JPEG image to the display at the specified position.
        
        Args:
            x: X coordinate to draw at
            y: Y coordinate to draw at
            scale: Optional scaling factor (default: 1)
        """
        if self._surface is None:
            raise RuntimeError("No JPEG file opened")
        
        # Get the actual pygame surface from the display
        if hasattr(self.display, '_surface'):
            target = self.display._surface
        else:
            target = self.display
        
        # Scale if needed
        if scale != 1:
            new_width = int(self._width * scale)
            new_height = int(self._height * scale)
            scaled = pygame.transform.scale(self._surface, (new_width, new_height))
            target.blit(scaled, (int(x), int(y)))
        else:
            target.blit(self._surface, (int(x), int(y)))
