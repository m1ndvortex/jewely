"""
Template tags for image optimization (Task 28.3)

Provides lazy loading support for images to improve page load performance.
"""

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def lazy_img(src, alt="", css_class="", width="", height="", **kwargs):
    """
    Render an image tag with lazy loading enabled.
    
    Usage:
        {% lazy_img "path/to/image.jpg" alt="Description" css_class="w-full h-auto" %}
    
    Args:
        src: Image source URL
        alt: Alt text for accessibility
        css_class: CSS classes to apply
        width: Image width attribute
        height: Image height attribute
        **kwargs: Additional HTML attributes
    
    Returns:
        HTML img tag with loading="lazy" attribute
    """
    # Build attributes
    attrs = {
        "src": src,
        "alt": alt,
        "loading": "lazy",  # Native lazy loading
        "decoding": "async",  # Async image decoding
    }
    
    if css_class:
        attrs["class"] = css_class
    
    if width:
        attrs["width"] = width
    
    if height:
        attrs["height"] = height
    
    # Add any additional attributes
    attrs.update(kwargs)
    
    # Build the img tag
    attr_str = " ".join(f'{key}="{value}"' for key, value in attrs.items())
    img_tag = f"<img {attr_str}>"
    
    return mark_safe(img_tag)


@register.filter
def add_lazy_loading(img_html):
    """
    Add lazy loading attributes to existing img tags.
    
    Usage:
        {{ some_html_with_images|add_lazy_loading }}
    
    Args:
        img_html: HTML string containing img tags
    
    Returns:
        HTML string with lazy loading attributes added to img tags
    """
    import re
    
    # Pattern to match img tags without loading attribute
    pattern = r'<img(?![^>]*loading=)([^>]*)>'
    
    # Replacement function
    def add_attrs(match):
        attrs = match.group(1)
        return f'<img{attrs} loading="lazy" decoding="async">'
    
    # Replace all matching img tags
    result = re.sub(pattern, add_attrs, str(img_html))
    
    return mark_safe(result)
