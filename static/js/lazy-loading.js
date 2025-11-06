/**
 * Lazy Loading Utilities (Task 28.3)
 * 
 * Provides JavaScript utilities for lazy loading images and other content
 * for browsers that don't support native lazy loading.
 */

(function() {
    'use strict';
    
    /**
     * Check if browser supports native lazy loading
     */
    const supportsNativeLazyLoading = 'loading' in HTMLImageElement.prototype;
    
    /**
     * Lazy load images using Intersection Observer for older browsers
     */
    function lazyLoadImages() {
        // If browser supports native lazy loading, no need for polyfill
        if (supportsNativeLazyLoading) {
            return;
        }
        
        const images = document.querySelectorAll('img[loading="lazy"]');
        
        if ('IntersectionObserver' in window) {
            // Use Intersection Observer for modern browsers without native lazy loading
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        
                        // Load the image
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                        }
                        
                        // Load srcset if present
                        if (img.dataset.srcset) {
                            img.srcset = img.dataset.srcset;
                        }
                        
                        // Remove loading attribute
                        img.removeAttribute('loading');
                        
                        // Stop observing this image
                        observer.unobserve(img);
                    }
                });
            }, {
                // Load images 50px before they enter viewport
                rootMargin: '50px 0px',
                threshold: 0.01
            });
            
            images.forEach(img => imageObserver.observe(img));
        } else {
            // Fallback for very old browsers - load all images immediately
            images.forEach(img => {
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                }
                if (img.dataset.srcset) {
                    img.srcset = img.dataset.srcset;
                }
                img.removeAttribute('loading');
            });
        }
    }
    
    /**
     * Add lazy loading to dynamically added images
     */
    function observeDynamicImages() {
        if (!('MutationObserver' in window)) {
            return;
        }
        
        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1) { // Element node
                        // Check if the node itself is an image
                        if (node.tagName === 'IMG' && node.getAttribute('loading') === 'lazy') {
                            lazyLoadImages();
                        }
                        
                        // Check for images within the node
                        const images = node.querySelectorAll && node.querySelectorAll('img[loading="lazy"]');
                        if (images && images.length > 0) {
                            lazyLoadImages();
                        }
                    }
                });
            });
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }
    
    /**
     * Initialize lazy loading
     */
    function init() {
        // Initial lazy load
        lazyLoadImages();
        
        // Observe for dynamically added images
        observeDynamicImages();
        
        // Re-check on HTMX content swap
        if (typeof htmx !== 'undefined') {
            document.body.addEventListener('htmx:afterSwap', lazyLoadImages);
            document.body.addEventListener('htmx:afterSettle', lazyLoadImages);
        }
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    // Export for manual use
    window.lazyLoadImages = lazyLoadImages;
})();
