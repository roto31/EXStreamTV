//
//  Logger.swift
//  EXStreamTVApp
//
//  Logging utility for the macOS app.
//

import Foundation
import os.log

// MARK: - Logger

enum AppLogger {
    private static let subsystem = "com.exstreamtv.app"
    
    static let general = Logger(subsystem: subsystem, category: "general")
    static let server = Logger(subsystem: subsystem, category: "server")
    static let network = Logger(subsystem: subsystem, category: "network")
    static let ui = Logger(subsystem: subsystem, category: "ui")
}

// MARK: - Log Level

enum LogLevel: String, CaseIterable {
    case debug = "DEBUG"
    case info = "INFO"
    case warning = "WARNING"
    case error = "ERROR"
    
    var osLogType: OSLogType {
        switch self {
        case .debug: return .debug
        case .info: return .info
        case .warning: return .default
        case .error: return .error
        }
    }
}

// MARK: - Log Entry

struct LogEntry: Identifiable, Codable {
    let id: UUID
    let timestamp: Date
    let level: String
    let category: String
    let message: String
    
    init(level: LogLevel, category: String, message: String) {
        self.id = UUID()
        self.timestamp = Date()
        self.level = level.rawValue
        self.category = category
        self.message = message
    }
}

// MARK: - Log Manager

class LogManager: ObservableObject {
    static let shared = LogManager()
    
    @Published var entries: [LogEntry] = []
    
    private let maxEntries = 1000
    private let queue = DispatchQueue(label: "com.exstreamtv.logmanager")
    
    private init() {}
    
    func log(_ level: LogLevel, category: String, message: String) {
        let entry = LogEntry(level: level, category: category, message: message)
        
        queue.async {
            DispatchQueue.main.async {
                self.entries.insert(entry, at: 0)
                if self.entries.count > self.maxEntries {
                    self.entries.removeLast()
                }
            }
        }
        
        // Also log to system
        switch level {
        case .debug:
            AppLogger.general.debug("\(message)")
        case .info:
            AppLogger.general.info("\(message)")
        case .warning:
            AppLogger.general.warning("\(message)")
        case .error:
            AppLogger.general.error("\(message)")
        }
    }
    
    func clear() {
        entries.removeAll()
    }
    
    func exportLogs() -> URL? {
        let fileManager = FileManager.default
        let tempDir = fileManager.temporaryDirectory
        let logFile = tempDir.appendingPathComponent("exstreamtv_logs_\(Date().timeIntervalSince1970).txt")
        
        var content = "EXStreamTV Logs Export\n"
        content += "Generated: \(Date())\n"
        content += String(repeating: "=", count: 50) + "\n\n"
        
        for entry in entries {
            content += "[\(entry.timestamp)] [\(entry.level)] [\(entry.category)] \(entry.message)\n"
        }
        
        do {
            try content.write(to: logFile, atomically: true, encoding: .utf8)
            return logFile
        } catch {
            AppLogger.general.error("Failed to export logs: \(error.localizedDescription)")
            return nil
        }
    }
}
