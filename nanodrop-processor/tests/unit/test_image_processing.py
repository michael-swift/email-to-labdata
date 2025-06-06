import pytest
from PIL import Image
import io
import numpy as np
from tests.fixtures.image_generator import NanodropImageGenerator, generate_test_images
from tests.fixtures.nanodrop_samples import NANODROP_SAMPLES


class TestImageProcessing:
    """Test image processing functionality."""
    
    @pytest.fixture
    def test_images(self):
        """Generate test images for all tests."""
        return generate_test_images()
    
    @pytest.fixture
    def image_generator(self):
        """Create image generator instance."""
        return NanodropImageGenerator()
    
    @pytest.mark.unit
    def test_image_generation(self, image_generator):
        """Test that we can generate valid test images."""
        sample_data = NANODROP_SAMPLES["high_quality_dna"]
        image_bytes = image_generator.generate_image(sample_data)
        
        # Verify it's valid image data
        img = Image.open(io.BytesIO(image_bytes))
        assert img.format == "JPEG"
        assert img.size == (800, 480)
        assert img.mode == "RGB"
    
    @pytest.mark.unit
    def test_image_effects(self, image_generator):
        """Test that image effects are applied correctly."""
        sample_data = NANODROP_SAMPLES["high_quality_dna"]
        
        # Test blur
        blurred_bytes = image_generator.generate_image(sample_data, blur_level=3)
        blurred_img = Image.open(io.BytesIO(blurred_bytes))
        assert blurred_img is not None
        
        # Test rotation
        rotated_bytes = image_generator.generate_image(sample_data, rotation=45)
        rotated_img = Image.open(io.BytesIO(rotated_bytes))
        # Rotated image should be larger due to expansion
        assert rotated_img.size[0] > 800 or rotated_img.size[1] > 480
        
        # Test noise
        noisy_bytes = image_generator.generate_image(sample_data, add_noise=True)
        noisy_img = Image.open(io.BytesIO(noisy_bytes))
        assert noisy_img is not None
    
    @pytest.mark.unit
    def test_all_sample_types(self, image_generator):
        """Test image generation for all sample types."""
        for sample_name, sample_data in NANODROP_SAMPLES.items():
            image_bytes = image_generator.generate_image(sample_data)
            img = Image.open(io.BytesIO(image_bytes))
            
            assert img is not None
            assert img.size == (800, 480)
            assert img.format == "JPEG"
    
    @pytest.mark.unit
    def test_image_metadata_extraction(self, test_images):
        """Test extracting basic metadata from images."""
        for img_name, img_bytes in test_images.items():
            img = Image.open(io.BytesIO(img_bytes))
            
            # Check basic properties
            assert hasattr(img, 'size')
            assert hasattr(img, 'mode')
            assert hasattr(img, 'format')
            
            # Verify reasonable file size
            assert len(img_bytes) > 1000  # At least 1KB
            assert len(img_bytes) < 500000  # Less than 500KB
    
    @pytest.mark.unit
    def test_image_quality_assessment(self, test_images):
        """Test assessing image quality for processing."""
        def assess_image_quality(img_bytes):
            img = Image.open(io.BytesIO(img_bytes))
            
            # Convert to numpy array for analysis
            img_array = np.array(img)
            
            # Check contrast
            contrast = img_array.std()
            
            # Check brightness
            brightness = img_array.mean()
            
            # Simple quality score
            quality_score = {
                "contrast": contrast,
                "brightness": brightness,
                "is_color": len(img_array.shape) == 3,
                "has_good_contrast": contrast > 30,
                "has_good_brightness": 50 < brightness < 200
            }
            
            return quality_score
        
        # Test perfect image
        perfect_quality = assess_image_quality(test_images["perfect"])
        assert perfect_quality["has_good_contrast"]
        assert perfect_quality["has_good_brightness"]
        
        # Test blurry image (should still be processable)
        blurry_quality = assess_image_quality(test_images["slightly_blurry"])
        assert blurry_quality["is_color"]
    
    @pytest.mark.unit
    def test_image_preprocessing_pipeline(self, sample_image_bytes):
        """Test a simple preprocessing pipeline."""
        # This is a placeholder for actual preprocessing
        # In real implementation, this would enhance the image
        
        img = Image.open(io.BytesIO(sample_image_bytes))
        
        # Example preprocessing steps
        # 1. Check if image needs rotation
        if img.size[0] < img.size[1]:
            # Image is portrait, might need rotation
            img = img.rotate(90, expand=True)
        
        # 2. Resize if too large
        max_dimension = 2048
        if img.size[0] > max_dimension or img.size[1] > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        
        # 3. Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Verify preprocessing worked
        assert img.mode == 'RGB'
        assert img.size[0] <= max_dimension
        assert img.size[1] <= max_dimension


class TestImageValidation:
    """Test image validation functionality."""
    
    @pytest.mark.unit
    def test_validate_image_format(self, sample_image_bytes):
        """Test validating image format."""
        def is_valid_image(img_bytes):
            try:
                img = Image.open(io.BytesIO(img_bytes))
                return img.format in ['JPEG', 'PNG', 'BMP', 'TIFF']
            except:
                return False
        
        assert is_valid_image(sample_image_bytes)
        
        # Test invalid data
        assert not is_valid_image(b"not an image")
        assert not is_valid_image(b"")
    
    @pytest.mark.unit
    def test_validate_image_size(self, sample_image_bytes):
        """Test validating image size constraints."""
        def validate_image_size(img_bytes, max_size_mb=25):
            size_mb = len(img_bytes) / (1024 * 1024)
            return size_mb <= max_size_mb
        
        assert validate_image_size(sample_image_bytes)
        assert validate_image_size(sample_image_bytes, max_size_mb=1)
        
        # Create a fake large image
        large_data = b"x" * (26 * 1024 * 1024)
        assert not validate_image_size(large_data, max_size_mb=25)
    
    @pytest.mark.unit
    def test_validate_image_dimensions(self, test_images):
        """Test validating image dimensions."""
        def validate_dimensions(img_bytes, min_width=200, min_height=150):
            try:
                img = Image.open(io.BytesIO(img_bytes))
                return img.size[0] >= min_width and img.size[1] >= min_height
            except:
                return False
        
        # All test images should meet minimum dimensions
        for img_name, img_bytes in test_images.items():
            assert validate_dimensions(img_bytes)