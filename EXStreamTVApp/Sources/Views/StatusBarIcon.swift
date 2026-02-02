//
//  StatusBarIcon.swift
//  EXStreamTVApp
//
//  Dynamic menu bar icon generation with color-coded states and badges.
//

import AppKit

/// Generates dynamic menu bar icons based on server state.
class StatusBarIcon {
    // MARK: - State Enum
    
    enum State {
        case stopped      // Gray - server is not running
        case starting     // Yellow/pulsing - server is starting
        case running      // Green - server is running normally
        case stopping     // Yellow/pulsing - server is stopping
        case error        // Red - server has an error
        
        var color: NSColor {
            switch self {
            case .stopped:
                return .systemGray
            case .starting, .stopping:
                return .systemYellow
            case .running:
                return .systemGreen
            case .error:
                return .systemRed
            }
        }
        
        var symbolName: String {
            switch self {
            case .stopped:
                return "tv"
            case .starting, .stopping:
                return "tv.circle"
            case .running:
                return "tv.fill"
            case .error:
                return "tv.inset.filled"
            }
        }
    }
    
    // MARK: - Properties
    
    private var animationTimer: Timer?
    private var animationFrame: Int = 0
    private var currentState: State = .stopped
    
    // Cache for generated icons
    private var iconCache: [String: NSImage] = [:]
    
    // MARK: - Initialization
    
    init() {}
    
    deinit {
        animationTimer?.invalidate()
    }
    
    // MARK: - Icon Generation
    
    /// Generates a menu bar icon for the given state
    /// - Parameters:
    ///   - state: The current server state
    ///   - activeStreams: Number of active streams (shown as badge if > 0)
    /// - Returns: The generated NSImage for the status bar
    func icon(for state: State, activeStreams: Int = 0) -> NSImage {
        let cacheKey = "\(state)-\(activeStreams)"
        
        // Return cached icon if available
        if let cached = iconCache[cacheKey] {
            return cached
        }
        
        let icon = generateIcon(for: state, activeStreams: activeStreams)
        iconCache[cacheKey] = icon
        return icon
    }
    
    /// Generates an array of icons for animation during transitions
    /// - Parameter state: The transitioning state
    /// - Returns: Array of NSImages for animation frames
    func animatedIcons(for state: State) -> [NSImage] {
        guard state == .starting || state == .stopping else {
            return [icon(for: state)]
        }
        
        var frames: [NSImage] = []
        let baseColor = state.color
        
        // Create 4 frames with varying opacity
        let opacities: [CGFloat] = [0.3, 0.6, 1.0, 0.6]
        
        for (index, opacity) in opacities.enumerated() {
            let image = generateBaseIcon(symbolName: state.symbolName)
            let tintedImage = image.tinted(with: baseColor.withAlphaComponent(opacity))
            frames.append(tintedImage)
        }
        
        return frames
    }
    
    // MARK: - Private Methods
    
    private func generateIcon(for state: State, activeStreams: Int) -> NSImage {
        let baseIcon = generateBaseIcon(symbolName: state.symbolName)
        var finalIcon = baseIcon.tinted(with: state.color)
        
        // Add badge for active streams
        if activeStreams > 0 && state == .running {
            finalIcon = addBadge(to: finalIcon, count: activeStreams)
        }
        
        return finalIcon
    }
    
    private func generateBaseIcon(symbolName: String) -> NSImage {
        let config = NSImage.SymbolConfiguration(pointSize: 16, weight: .regular)
        
        guard let image = NSImage(systemSymbolName: symbolName, accessibilityDescription: "EXStreamTV")?
            .withSymbolConfiguration(config) else {
            // Fallback to a basic TV icon
            return NSImage(systemSymbolName: "tv", accessibilityDescription: "EXStreamTV") ?? NSImage()
        }
        
        // Set as template for proper menu bar rendering
        let templateImage = image.copy() as! NSImage
        templateImage.isTemplate = false // We handle colors ourselves
        
        return templateImage
    }
    
    private func addBadge(to image: NSImage, count: Int) -> NSImage {
        let size = NSSize(width: 22, height: 18)
        let newImage = NSImage(size: size)
        
        newImage.lockFocus()
        
        // Draw the base icon
        let iconRect = NSRect(x: 0, y: 0, width: 16, height: 16)
        image.draw(in: iconRect)
        
        // Draw the badge
        let badgeText = count > 9 ? "9+" : "\(count)"
        let badgeFont = NSFont.systemFont(ofSize: 9, weight: .bold)
        let badgeAttributes: [NSAttributedString.Key: Any] = [
            .font: badgeFont,
            .foregroundColor: NSColor.white
        ]
        
        let textSize = (badgeText as NSString).size(withAttributes: badgeAttributes)
        let badgeWidth = max(textSize.width + 4, 12)
        let badgeHeight: CGFloat = 12
        let badgeX = size.width - badgeWidth
        let badgeY = size.height - badgeHeight
        
        // Badge background
        let badgeRect = NSRect(x: badgeX, y: badgeY, width: badgeWidth, height: badgeHeight)
        let badgePath = NSBezierPath(roundedRect: badgeRect, xRadius: badgeHeight / 2, yRadius: badgeHeight / 2)
        NSColor.systemGreen.setFill()
        badgePath.fill()
        
        // Badge text
        let textX = badgeRect.midX - textSize.width / 2
        let textY = badgeRect.midY - textSize.height / 2 + 1
        (badgeText as NSString).draw(at: NSPoint(x: textX, y: textY), withAttributes: badgeAttributes)
        
        newImage.unlockFocus()
        
        return newImage
    }
    
    // MARK: - Animation Control
    
    /// Starts an animation for transitioning states
    func startAnimation(on statusItem: NSStatusItem, for state: State) {
        stopAnimation()
        
        guard state == .starting || state == .stopping else { return }
        
        currentState = state
        let frames = animatedIcons(for: state)
        
        animationTimer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self, weak statusItem] timer in
            guard let self = self, let statusItem = statusItem else {
                timer.invalidate()
                return
            }
            
            DispatchQueue.main.async {
                self.animationFrame = (self.animationFrame + 1) % frames.count
                statusItem.button?.image = frames[self.animationFrame]
            }
        }
    }
    
    /// Stops any ongoing animation
    func stopAnimation() {
        animationTimer?.invalidate()
        animationTimer = nil
        animationFrame = 0
    }
    
    /// Clears the icon cache (useful if colors change)
    func clearCache() {
        iconCache.removeAll()
    }
}

// MARK: - NSImage Extension

private extension NSImage {
    func tinted(with color: NSColor) -> NSImage {
        guard let cgImage = self.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
            return self
        }
        
        let size = self.size
        let newImage = NSImage(size: size)
        
        newImage.lockFocus()
        
        guard let context = NSGraphicsContext.current?.cgContext else {
            newImage.unlockFocus()
            return self
        }
        
        // Draw the image
        let rect = CGRect(origin: .zero, size: size)
        context.draw(cgImage, in: rect)
        
        // Apply color with sourceAtop blend mode
        context.setBlendMode(.sourceAtop)
        context.setFillColor(color.cgColor)
        context.fill(rect)
        
        newImage.unlockFocus()
        
        return newImage
    }
}
