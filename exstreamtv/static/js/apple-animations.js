/**
 * Apple.com Animation Library
 * Smooth scroll, fade-ins, parallax, and micro-interactions
 * Matching Apple.com's exact animation feel
 */

(function() {
    'use strict';
    
    // ============================================
    // CONFIGURATION
    // ============================================
    
    const CONFIG = {
        // Animation timing
        duration: {
            fast: 200,
            normal: 300,
            slow: 600
        },
        
        // Easing functions (Apple standard)
        easing: {
            apple: 'cubic-bezier(0.4, 0.0, 0.2, 1)',
            appleIn: 'cubic-bezier(0.4, 0.0, 1, 1)',
            appleOut: 'cubic-bezier(0.0, 0.0, 0.2, 1)',
            appleInOut: 'cubic-bezier(0.4, 0.0, 0.2, 1)'
        },
        
        // Intersection Observer settings
        intersection: {
            rootMargin: '0px 0px -20% 0px', // Trigger at 20% viewport
            threshold: [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        },
        
        // Parallax settings
        parallax: {
            multiplier: 0.1, // Subtle parallax
            maxMultiplier: 0.3
        },
        
        // Performance
        useRAF: true, // Use requestAnimationFrame
        debounceDelay: 16 // ~60fps
    };
    
    // ============================================
    // UTILITY FUNCTIONS
    // ============================================
    
    /**
     * Check if user prefers reduced motion
     */
    function prefersReducedMotion() {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }
    
    /**
     * Debounce function for performance
     */
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    /**
     * Throttle function using requestAnimationFrame
     */
    function throttleRAF(func) {
        let rafId = null;
        return function(...args) {
            if (rafId === null) {
                rafId = requestAnimationFrame(() => {
                    func(...args);
                    rafId = null;
                });
            }
        };
    }
    
    /**
     * Check if element is in viewport
     */
    function isInViewport(element, threshold = 0) {
        const rect = element.getBoundingClientRect();
        const windowHeight = window.innerHeight || document.documentElement.clientHeight;
        const windowWidth = window.innerWidth || document.documentElement.clientWidth;
        
        return (
            rect.top >= -threshold &&
            rect.left >= -threshold &&
            rect.bottom <= windowHeight + threshold &&
            rect.right <= windowWidth + threshold
        );
    }
    
    // ============================================
    // SMOOTH SCROLL
    // ============================================
    
    /**
     * Smooth scroll to element
     */
    function smoothScrollTo(target, options = {}) {
        if (prefersReducedMotion()) {
            target.scrollIntoView({ behavior: 'auto', block: 'start' });
            return;
        }
        
        const defaultOptions = {
            behavior: 'smooth',
            block: 'start',
            inline: 'nearest',
            offset: 0
        };
        
        const finalOptions = { ...defaultOptions, ...options };
        
        if (finalOptions.offset) {
            const elementPosition = target.getBoundingClientRect().top + window.pageYOffset;
            const offsetPosition = elementPosition - finalOptions.offset;
            
            window.scrollTo({
                top: offsetPosition,
                behavior: 'smooth'
            });
        } else {
            target.scrollIntoView(finalOptions);
        }
    }
    
    /**
     * Initialize smooth scroll for anchor links
     */
    function initSmoothScroll() {
        if (prefersReducedMotion()) return;
        
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function(e) {
                const href = this.getAttribute('href');
                if (href === '#' || href === '#!') return;
                
                const target = document.querySelector(href);
                if (target) {
                    e.preventDefault();
                    smoothScrollTo(target, { offset: 80 }); // Account for sticky nav
                }
            });
        });
    }
    
    // ============================================
    // FADE-IN ANIMATIONS (Intersection Observer)
    // ============================================
    
    /**
     * Fade-in animation controller
     */
    class FadeInController {
        constructor() {
            this.observer = null;
            this.elements = [];
            this.init();
        }
        
        init() {
            if (prefersReducedMotion()) {
                // Show all elements immediately
                document.querySelectorAll('.animate-on-scroll').forEach(el => {
                    el.classList.add('visible');
                });
                return;
            }
            
            // Create Intersection Observer
            this.observer = new IntersectionObserver(
                (entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            entry.target.classList.add('visible');
                            // Unobserve after animation
                            this.observer.unobserve(entry.target);
                        }
                    });
                },
                CONFIG.intersection
            );
            
            // Observe all elements with animate-on-scroll class
            document.querySelectorAll('.animate-on-scroll').forEach(el => {
                this.observer.observe(el);
            });
        }
        
        observe(element) {
            if (this.observer && !prefersReducedMotion()) {
                this.observer.observe(element);
            } else {
                element.classList.add('visible');
            }
        }
        
        unobserve(element) {
            if (this.observer) {
                this.observer.unobserve(element);
            }
        }
    }
    
    // ============================================
    // PARALLAX EFFECTS
    // ============================================
    
    /**
     * Parallax controller
     */
    class ParallaxController {
        constructor() {
            this.elements = [];
            this.isActive = !prefersReducedMotion();
            this.lastScrollY = window.scrollY;
            this.ticking = false;
            this.init();
        }
        
        init() {
            if (!this.isActive) return;
            
            // Find all parallax elements
            this.elements = Array.from(document.querySelectorAll('.parallax-element'));
            
            if (this.elements.length === 0) return;
            
            // Bind scroll handler
            const scrollHandler = throttleRAF(() => {
                this.update();
            });
            
            window.addEventListener('scroll', scrollHandler, { passive: true });
            window.addEventListener('resize', debounce(() => this.update(), CONFIG.debounceDelay));
            
            // Initial update
            this.update();
        }
        
        update() {
            if (!this.isActive) return;
            
            const scrollY = window.scrollY;
            const windowHeight = window.innerHeight;
            
            this.elements.forEach(element => {
                const rect = element.getBoundingClientRect();
                const elementTop = rect.top + scrollY;
                const elementHeight = rect.height;
                
                // Calculate if element is in viewport
                if (rect.bottom < 0 || rect.top > windowHeight) {
                    return; // Element not visible
                }
                
                // Get parallax multiplier from data attribute or use default
                const multiplier = parseFloat(element.dataset.parallaxSpeed) || CONFIG.parallax.multiplier;
                const clampedMultiplier = Math.min(multiplier, CONFIG.parallax.maxMultiplier);
                
                // Calculate parallax offset
                const elementCenter = elementTop + elementHeight / 2;
                const viewportCenter = scrollY + windowHeight / 2;
                const distance = viewportCenter - elementCenter;
                const offset = distance * clampedMultiplier;
                
                // Apply transform
                element.style.transform = `translate3d(0, ${offset}px, 0)`;
            });
        }
    }
    
    // ============================================
    // MICRO-INTERACTIONS
    // ============================================
    
    /**
     * Enhanced button press feedback
     */
    function initButtonInteractions() {
        document.querySelectorAll('.btn-apple, .btn').forEach(button => {
            if (prefersReducedMotion()) return;
            
            button.addEventListener('mousedown', function() {
                this.style.transform = 'scale(0.96)';
            });
            
            button.addEventListener('mouseup', function() {
                this.style.transform = '';
            });
            
            button.addEventListener('mouseleave', function() {
                this.style.transform = '';
            });
        });
    }
    
    /**
     * Card hover lift effect
     */
    function initCardInteractions() {
        if (prefersReducedMotion()) return;
        
        document.querySelectorAll('.card-apple, .card').forEach(card => {
            card.addEventListener('mouseenter', function() {
                if (!this.classList.contains('no-hover')) {
                    this.style.willChange = 'transform, box-shadow';
                }
            });
            
            card.addEventListener('mouseleave', function() {
                this.style.willChange = '';
            });
        });
    }
    
    // ============================================
    // PAGE TRANSITIONS
    // ============================================
    
    /**
     * Page transition manager
     */
    class PageTransitionManager {
        constructor() {
            this.init();
        }
        
        init() {
            if (prefersReducedMotion()) return;
            
            // Fade out on navigation
            document.querySelectorAll('a[href^="/"]:not([target="_blank"]):not([href^="#"]):not([href^="http"])').forEach(link => {
                link.addEventListener('click', (e) => {
                    // Only for same-origin navigation
                    if (link.hostname === window.location.hostname || !link.hostname) {
                        // Add fade-out class to body
                        document.body.style.opacity = '0';
                        document.body.style.transition = `opacity ${CONFIG.duration.fast}ms ${CONFIG.easing.apple}`;
                    }
                });
            });
        }
    }
    
    // ============================================
    // STICKY NAVIGATION ENHANCEMENTS
    // ============================================
    
    /**
     * Enhanced sticky navigation
     */
    function initStickyNav() {
        const nav = document.querySelector('.nav-apple-sticky, .app-bar');
        if (!nav) return;
        
        const scrollHandler = throttleRAF(() => {
            if (window.scrollY > 20) {
                nav.classList.add('scrolled');
            } else {
                nav.classList.remove('scrolled');
            }
        });
        
        window.addEventListener('scroll', scrollHandler, { passive: true });
    }
    
    // ============================================
    // LAZY LOADING FOR IMAGES
    // ============================================
    
    /**
     * Lazy load images with fade-in
     */
    function initLazyLoading() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            img.removeAttribute('data-src');
                        }
                        
                        if (img.dataset.srcset) {
                            img.srcset = img.dataset.srcset;
                            img.removeAttribute('data-srcset');
                        }
                        
                        img.classList.add('loaded');
                        observer.unobserve(img);
                    }
                });
            }, {
                rootMargin: '50px'
            });
            
            document.querySelectorAll('img[data-src]').forEach(img => {
                imageObserver.observe(img);
            });
        }
    }
    
    // ============================================
    // INITIALIZATION
    // ============================================
    
    /**
     * Initialize all animations
     */
    function init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }
        
        // Initialize components
        initSmoothScroll();
        
        const fadeInController = new FadeInController();
        window.appleFadeInController = fadeInController; // Expose globally
        
        const parallaxController = new ParallaxController();
        window.appleParallaxController = parallaxController; // Expose globally
        
        initButtonInteractions();
        initCardInteractions();
        initStickyNav();
        initLazyLoading();
        
        const pageTransitionManager = new PageTransitionManager();
        window.applePageTransitionManager = pageTransitionManager; // Expose globally
        
        // Observe dynamically added elements
        if (window.MutationObserver) {
            const mutationObserver = new MutationObserver(mutations => {
                mutations.forEach(mutation => {
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === 1) { // Element node
                            // Check for animate-on-scroll elements
                            if (node.classList && node.classList.contains('animate-on-scroll')) {
                                fadeInController.observe(node);
                            }
                            
                            // Check for parallax elements
                            if (node.classList && node.classList.contains('parallax-element')) {
                                parallaxController.elements.push(node);
                            }
                            
                            // Check for lazy images
                            if (node.tagName === 'IMG' && node.dataset.src) {
                                const imageObserver = new IntersectionObserver((entries, observer) => {
                                    entries.forEach(entry => {
                                        if (entry.isIntersecting) {
                                            const img = entry.target;
                                            if (img.dataset.src) {
                                                img.src = img.dataset.src;
                                                img.removeAttribute('data-src');
                                                img.classList.add('loaded');
                                                observer.unobserve(img);
                                            }
                                        }
                                    });
                                }, { rootMargin: '50px' });
                                imageObserver.observe(node);
                            }
                        }
                    });
                });
            });
            
            mutationObserver.observe(document.body, {
                childList: true,
                subtree: true
            });
        }
    }
    
    // Auto-initialize
    init();
    
    // Expose API globally
    window.AppleAnimations = {
        smoothScrollTo,
        fadeInController: null, // Will be set after init
        parallaxController: null, // Will be set after init
        init
    };
    
    // Set controllers after init
    setTimeout(() => {
        window.AppleAnimations.fadeInController = window.appleFadeInController;
        window.AppleAnimations.parallaxController = window.appleParallaxController;
    }, 100);
    
})();

