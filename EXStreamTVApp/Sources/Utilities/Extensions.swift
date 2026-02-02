//
//  Extensions.swift
//  EXStreamTVApp
//
//  Utility extensions.
//

import Foundation
import SwiftUI

// MARK: - Color Extensions

extension Color {
    static let appPrimary = Color.accentColor
    static let appSuccess = Color.green
    static let appWarning = Color.orange
    static let appError = Color.red
    
    static let surfaceBackground = Color(NSColor.windowBackgroundColor)
    static let surfaceSecondary = Color(NSColor.controlBackgroundColor)
}

// MARK: - View Extensions

extension View {
    func cardStyle() -> some View {
        self
            .padding()
            .background(Color.surfaceSecondary)
            .cornerRadius(10)
    }
    
    @ViewBuilder
    func `if`<Content: View>(_ condition: Bool, transform: (Self) -> Content) -> some View {
        if condition {
            transform(self)
        } else {
            self
        }
    }
}

// MARK: - Date Extensions

extension Date {
    var relativeFormatted: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: self, relativeTo: Date())
    }
    
    var timeFormatted: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return formatter.string(from: self)
    }
}

// MARK: - TimeInterval Extensions

extension TimeInterval {
    var formattedDuration: String {
        let hours = Int(self) / 3600
        let minutes = Int(self) % 3600 / 60
        let seconds = Int(self) % 60
        
        if hours > 0 {
            return String(format: "%d:%02d:%02d", hours, minutes, seconds)
        } else {
            return String(format: "%d:%02d", minutes, seconds)
        }
    }
    
    var shortDuration: String {
        let hours = Int(self) / 3600
        let minutes = Int(self) % 3600 / 60
        
        if hours > 0 {
            return "\(hours)h \(minutes)m"
        } else {
            return "\(minutes)m"
        }
    }
}

// MARK: - Int Extensions

extension Int {
    var formattedWithSeparator: String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        return formatter.string(from: NSNumber(value: self)) ?? "\(self)"
    }
}

// MARK: - Bundle Extensions

extension Bundle {
    var appName: String {
        return object(forInfoDictionaryKey: "CFBundleName") as? String ?? "EXStreamTV"
    }
    
    var appVersion: String {
        return object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0"
    }
    
    var buildNumber: String {
        return object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "1"
    }
}

// MARK: - URL Extensions

extension URL {
    var isReachable: Bool {
        do {
            return try checkResourceIsReachable()
        } catch {
            return false
        }
    }
}

// MARK: - String Extensions

extension String {
    var isValidPath: Bool {
        return FileManager.default.fileExists(atPath: self)
    }
    
    var isValidURL: Bool {
        return URL(string: self) != nil
    }
}
