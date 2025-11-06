"""
Tests for Image Template Tags (Task 28.3)
"""

from django.template import Context, Template
from django.test import TestCase


class TestImageTags(TestCase):
    """Test lazy loading image template tags"""

    def test_lazy_img_basic(self):
        """Test basic lazy_img tag usage"""
        template = Template("{% load image_tags %}" "{% lazy_img 'test.jpg' alt='Test Image' %}")
        context = Context({})
        output = template.render(context)

        # Check that output contains img tag with lazy loading
        self.assertIn("<img", output)
        self.assertIn('src="test.jpg"', output)
        self.assertIn('alt="Test Image"', output)
        self.assertIn('loading="lazy"', output)
        self.assertIn('decoding="async"', output)

    def test_lazy_img_with_css_class(self):
        """Test lazy_img tag with CSS class"""
        template = Template(
            "{% load image_tags %}" "{% lazy_img 'test.jpg' alt='Test' css_class='w-full h-auto' %}"
        )
        context = Context({})
        output = template.render(context)

        # Check that CSS class is applied
        self.assertIn('class="w-full h-auto"', output)

    def test_lazy_img_with_dimensions(self):
        """Test lazy_img tag with width and height"""
        template = Template(
            "{% load image_tags %}" "{% lazy_img 'test.jpg' alt='Test' width='800' height='600' %}"
        )
        context = Context({})
        output = template.render(context)

        # Check that dimensions are set
        self.assertIn('width="800"', output)
        self.assertIn('height="600"', output)

    def test_add_lazy_loading_filter(self):
        """Test add_lazy_loading filter"""
        template = Template("{% load image_tags %}" "{{ html_content|add_lazy_loading }}")
        context = Context({"html_content": '<img src="test.jpg" alt="Test">'})
        output = template.render(context)

        # Check that lazy loading attributes are added
        self.assertIn('loading="lazy"', output)
        self.assertIn('decoding="async"', output)

    def test_add_lazy_loading_preserves_existing(self):
        """Test that add_lazy_loading doesn't duplicate attributes"""
        template = Template("{% load image_tags %}" "{{ html_content|add_lazy_loading }}")
        context = Context({"html_content": '<img src="test.jpg" alt="Test" loading="lazy">'})
        output = template.render(context)

        # Should not add duplicate loading attribute
        # Count occurrences of loading="lazy"
        count = output.count('loading="lazy"')
        self.assertEqual(count, 1)
