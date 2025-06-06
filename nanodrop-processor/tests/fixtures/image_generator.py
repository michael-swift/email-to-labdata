"""
Generate mock Nanodrop screen images for testing.
"""

from PIL import Image, ImageDraw, ImageFont
import io
from typing import Dict, Tuple, Optional
import random
from .nanodrop_samples import NANODROP_SAMPLES, SCREEN_LAYOUTS


class NanodropImageGenerator:
    """Generate realistic Nanodrop screen images for testing."""
    
    def __init__(self, layout: str = "nanodrop_one"):
        self.layout = SCREEN_LAYOUTS.get(layout, SCREEN_LAYOUTS["nanodrop_one"])
        self.width = 800
        self.height = 480
        self.bg_color = (240, 240, 240)  # Light gray background
        self.text_color = (0, 0, 0)  # Black text
        self.accent_color = (0, 102, 204)  # Blue accent
        
    def generate_image(self, sample_data: Dict, 
                      add_noise: bool = False,
                      blur_level: int = 0,
                      rotation: int = 0) -> bytes:
        """
        Generate a Nanodrop screen image with the given data.
        
        Args:
            sample_data: Dictionary with nanodrop measurements
            add_noise: Add random noise to simulate photo artifacts
            blur_level: 0-5, level of blur to apply
            rotation: Degrees to rotate the image
        
        Returns:
            Image bytes in JPEG format
        """
        # Create base image
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw UI elements
        self._draw_header(draw)
        self._draw_measurements(draw, sample_data)
        self._draw_graph(draw, sample_data)
        self._draw_footer(draw)
        
        # Apply effects
        if add_noise:
            img = self._add_noise(img)
        
        if blur_level > 0:
            img = self._apply_blur(img, blur_level)
        
        if rotation != 0:
            img = img.rotate(rotation, expand=True, fillcolor=self.bg_color)
        
        # Convert to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG', quality=95)
        return img_bytes.getvalue()
    
    def _draw_header(self, draw: ImageDraw):
        """Draw the header section of the screen."""
        # Title bar
        draw.rectangle([(0, 0), (self.width, 60)], fill=self.accent_color)
        draw.text((20, 20), "NanoDrop One", fill=(255, 255, 255), font=None)
        
        # Date/time
        draw.text((self.width - 150, 20), "2024-01-15 14:32", 
                 fill=(255, 255, 255), font=None)
    
    def _draw_measurements(self, draw: ImageDraw, data: Dict):
        """Draw the measurement values."""
        # Sample ID
        if "sample_id" in data:
            draw.text((50, 80), f"Sample: {data['sample_id']}", 
                     fill=self.text_color, font=None)
        
        # Concentration (large, prominent)
        conc_text = f"{data.get('concentration', 0):.1f}"
        draw.text(self.layout["concentration_position"], conc_text, 
                 fill=self.text_color, font=None)
        
        # Unit
        unit_pos = (self.layout["concentration_position"][0] + 150,
                   self.layout["concentration_position"][1])
        draw.text(unit_pos, data.get('unit', 'ng/μL'), 
                 fill=self.text_color, font=None)
        
        # Absorbance values
        draw.text(self.layout["a260_position"], 
                 f"A260: {data.get('a260', 0):.3f}", 
                 fill=self.text_color, font=None)
        
        draw.text(self.layout["a280_position"], 
                 f"A280: {data.get('a280', 0):.3f}", 
                 fill=self.text_color, font=None)
        
        draw.text(self.layout["a230_position"], 
                 f"A230: {data.get('a230', 0):.3f}", 
                 fill=self.text_color, font=None)
        
        # Ratios
        draw.text(self.layout["ratio_260_280_position"], 
                 f"260/280: {data.get('ratio_260_280', 0):.2f}", 
                 fill=self.text_color, font=None)
        
        draw.text(self.layout["ratio_260_230_position"], 
                 f"260/230: {data.get('ratio_260_230', 0):.2f}", 
                 fill=self.text_color, font=None)
    
    def _draw_graph(self, draw: ImageDraw, data: Dict):
        """Draw a simple absorbance spectrum graph."""
        graph_pos = self.layout["graph_position"]
        graph_size = self.layout["graph_size"]
        
        # Graph background
        draw.rectangle([graph_pos, 
                       (graph_pos[0] + graph_size[0], 
                        graph_pos[1] + graph_size[1])],
                      fill=(255, 255, 255), outline=(200, 200, 200))
        
        # Draw axes
        # X-axis
        draw.line([(graph_pos[0], graph_pos[1] + graph_size[1] - 20),
                  (graph_pos[0] + graph_size[0], graph_pos[1] + graph_size[1] - 20)],
                 fill=(100, 100, 100), width=1)
        
        # Y-axis
        draw.line([(graph_pos[0] + 20, graph_pos[1]),
                  (graph_pos[0] + 20, graph_pos[1] + graph_size[1] - 20)],
                 fill=(100, 100, 100), width=1)
        
        # Draw a simple curve (simplified spectrum)
        points = self._generate_spectrum_points(data, graph_pos, graph_size)
        if len(points) > 1:
            draw.line(points, fill=self.accent_color, width=2)
        
        # Wavelength labels
        draw.text((graph_pos[0] + 50, graph_pos[1] + graph_size[1] - 10),
                 "230", fill=self.text_color, font=None)
        draw.text((graph_pos[0] + 120, graph_pos[1] + graph_size[1] - 10),
                 "260", fill=self.text_color, font=None)
        draw.text((graph_pos[0] + 190, graph_pos[1] + graph_size[1] - 10),
                 "280", fill=self.text_color, font=None)
    
    def _generate_spectrum_points(self, data: Dict, 
                                 graph_pos: Tuple[int, int], 
                                 graph_size: Tuple[int, int]) -> list:
        """Generate points for a simplified absorbance spectrum."""
        points = []
        
        # Map wavelengths to x positions
        wavelengths = [220, 230, 240, 250, 260, 270, 280, 290, 300]
        
        # Get absorbance values
        a230 = data.get('a230', 0)
        a260 = data.get('a260', 0)
        a280 = data.get('a280', 0)
        
        # Interpolate/extrapolate other points
        for i, wl in enumerate(wavelengths):
            x = graph_pos[0] + 20 + (i * (graph_size[0] - 40) / len(wavelengths))
            
            # Simple interpolation
            if wl == 230:
                abs_val = a230
            elif wl == 260:
                abs_val = a260
            elif wl == 280:
                abs_val = a280
            elif wl < 260:
                # Interpolate between 230 and 260
                ratio = (wl - 230) / 30
                abs_val = a230 + (a260 - a230) * ratio
            else:
                # Interpolate between 260 and 280
                ratio = (wl - 260) / 20
                abs_val = a260 + (a280 - a260) * ratio
            
            # Normalize to graph height
            max_abs = max(a230, a260, a280) * 1.2
            if max_abs > 0:
                y_normalized = abs_val / max_abs
            else:
                y_normalized = 0
            
            y = graph_pos[1] + graph_size[1] - 20 - (y_normalized * (graph_size[1] - 40))
            points.append((int(x), int(y)))
        
        return points
    
    def _draw_footer(self, draw: ImageDraw):
        """Draw footer information."""
        footer_y = self.height - 40
        draw.text((20, footer_y), "Path Length: 1.0 mm", 
                 fill=(100, 100, 100), font=None)
        draw.text((200, footer_y), "Factor: 50.0", 
                 fill=(100, 100, 100), font=None)
    
    def _add_noise(self, img: Image) -> Image:
        """Add random noise to simulate photo artifacts."""
        pixels = img.load()
        for i in range(img.width):
            for j in range(img.height):
                if random.random() < 0.02:  # 2% of pixels
                    # Add slight color variation
                    r, g, b = pixels[i, j]
                    noise = random.randint(-20, 20)
                    pixels[i, j] = (
                        max(0, min(255, r + noise)),
                        max(0, min(255, g + noise)),
                        max(0, min(255, b + noise))
                    )
        return img
    
    def _apply_blur(self, img: Image, level: int) -> Image:
        """Apply blur to simulate out-of-focus images."""
        from PIL import ImageFilter
        
        blur_filters = {
            1: ImageFilter.BLUR,
            2: ImageFilter.BoxBlur(2),
            3: ImageFilter.BoxBlur(3),
            4: ImageFilter.GaussianBlur(2),
            5: ImageFilter.GaussianBlur(4)
        }
        
        if level in blur_filters:
            return img.filter(blur_filters[level])
        return img


def generate_test_images() -> Dict[str, bytes]:
    """Generate a set of test images with various conditions."""
    generator = NanodropImageGenerator()
    test_images = {}
    
    # Perfect quality image
    test_images["perfect"] = generator.generate_image(
        NANODROP_SAMPLES["high_quality_dna"]
    )
    
    # Slightly blurry
    test_images["slightly_blurry"] = generator.generate_image(
        NANODROP_SAMPLES["high_quality_dna"],
        blur_level=2
    )
    
    # Very blurry
    test_images["very_blurry"] = generator.generate_image(
        NANODROP_SAMPLES["high_quality_dna"],
        blur_level=5
    )
    
    # Rotated
    test_images["rotated"] = generator.generate_image(
        NANODROP_SAMPLES["high_quality_dna"],
        rotation=15
    )
    
    # Noisy
    test_images["noisy"] = generator.generate_image(
        NANODROP_SAMPLES["high_quality_dna"],
        add_noise=True
    )
    
    # Different samples
    for sample_name, sample_data in NANODROP_SAMPLES.items():
        test_images[f"sample_{sample_name}"] = generator.generate_image(sample_data)
    
    return test_images