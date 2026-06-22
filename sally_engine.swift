import Foundation
import CoreGraphics
import ApplicationServices

let SALLY_INJECTED_TAG: Int64 = 0x53414C4C59 // Sally in hex plurb

// --- Injection Python to Swift ---
@_cdecl("check_accessibility")
public func checkAccessibility() -> Bool {
    let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
    return AXIsProcessTrustedWithOptions(options)
}

@_cdecl("inject_mouse")
public func injectMouse(x: Double, y: Double, button: Int32, isDown: Bool) {
    let point = CGPoint(x: x, y: y)
    var eventType: CGEventType
    if button == 0 { eventType = isDown ? .leftMouseDown : .leftMouseUp }
    else if button == 1 { eventType = isDown ? .rightMouseDown : .rightMouseUp }
    else { eventType = isDown ? .otherMouseDown : .otherMouseUp }
    
    guard let event = CGEvent(mouseEventSource: nil, mouseType: eventType, mouseCursorPosition: point, mouseButton: CGMouseButton(rawValue: UInt32(button))!) else { return }
    event.setIntegerValueField(.eventSourceUserData, value: SALLY_INJECTED_TAG)
    event.post(tap: .cghidEventTap)
}

@_cdecl("inject_key")
public func injectKey(keyCode: UInt16, isDown: Bool) {
    guard let event = CGEvent(keyboardEventSource: nil, virtualKey: keyCode, keyDown: isDown) else { return }
    event.setIntegerValueField(.eventSourceUserData, value: SALLY_INJECTED_TAG)
    event.post(tap: .cghidEventTap)
}

// --- Listening Swift to Python ---
public typealias KeyCallback = @convention(c) (UInt16, Bool) -> Void
public typealias MouseCallback = @convention(c) (Double, Double, Int32, Bool) -> Void

var globalEventTap: CFMachPort?
var runLoop: CFRunLoop?
var keyCallbackWrapper: KeyCallback?
var mouseCallbackWrapper: MouseCallback?

func eventTapCallback(proxy: CGEventTapProxy, type: CGEventType, event: CGEvent, refcon: UnsafeMutableRawPointer?) -> Unmanaged<CGEvent>? {
    let sourceTag = event.getIntegerValueField(.eventSourceUserData)
    if sourceTag == SALLY_INJECTED_TAG {
        return Unmanaged.passRetained(event)
    }

    if type == .keyDown || type == .keyUp {
        let keyCode = UInt16(event.getIntegerValueField(.keyboardEventKeycode))
        keyCallbackWrapper?(keyCode, type == .keyDown)
    } else if type == .leftMouseDown || type == .leftMouseUp || type == .rightMouseDown || type == .rightMouseUp || type == .otherMouseDown || type == .otherMouseUp {
        let loc = event.location
        var button: Int32 = 0
        if type == .rightMouseDown || type == .rightMouseUp { button = 1 }
        else if type == .otherMouseDown || type == .otherMouseUp { button = 2 }
        
        let isDown = (type == .leftMouseDown || type == .rightMouseDown || type == .otherMouseDown)
        mouseCallbackWrapper?(Double(loc.x), Double(loc.y), button, isDown)
    }
    if type == .flagsChanged {
            let keycode = UInt16(event.getIntegerValueField(.keyboardEventKeycode))
            let flags = event.flags
            var isDown = false
            
            // Translate Apple's flag state into a simple true/false for Python
            switch keycode {
            case 56: isDown = flags.contains(.maskShift)
            case 55: isDown = flags.contains(.maskCommand)
            case 58: isDown = flags.contains(.maskAlternate) // Option
            case 59: isDown = flags.contains(.maskControl)
            case 57: isDown = flags.contains(.maskAlphaShift) // Caps Lock
            default: break
            }
            
            keyCallbackWrapper?(keycode, isDown)
            return Unmanaged.passUnretained(event)
        }
    return Unmanaged.passRetained(event)
}

@_cdecl("start_listener")
public func startListener(kCb: @escaping KeyCallback, mCb: @escaping MouseCallback) {
    keyCallbackWrapper = kCb
    mouseCallbackWrapper = mCb
    
    let mask = (1 << CGEventType.keyDown.rawValue) | (1 << CGEventType.keyUp.rawValue) |
               (1 << CGEventType.leftMouseDown.rawValue) | (1 << CGEventType.leftMouseUp.rawValue) |
               (1 << CGEventType.rightMouseDown.rawValue) | (1 << CGEventType.rightMouseUp.rawValue) |
               (1 << CGEventType.otherMouseDown.rawValue) | (1 << CGEventType.otherMouseUp.rawValue) |
               (1 << CGEventType.flagsChanged.rawValue)
                    
    guard let tap = CGEvent.tapCreate(tap: .cgSessionEventTap, place: .headInsertEventTap, options: .defaultTap, eventsOfInterest: CGEventMask(mask), callback: eventTapCallback, userInfo: nil) else { return }
    
    globalEventTap = tap
    runLoop = CFRunLoopGetCurrent()
    let runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
    CFRunLoopAddSource(runLoop, runLoopSource, .commonModes)
    CGEvent.tapEnable(tap: tap, enable: true)
    CFRunLoopRun()
}

@_cdecl("stop_listener")
public func stopListener() {
    if let tap = globalEventTap { CGEvent.tapEnable(tap: tap, enable: false) }
    if let rl = runLoop { CFRunLoopStop(rl) }
}

@_cdecl("inject_mouse_current")
public func injectMouseCurrent(button: Int32, isDown: Bool) {
    // Create a temporary event so we can determine the
    // current cursor position on the screen.
    guard let locationEvent = CGEvent(source: nil) else {
        return
    }
    let cursorPosition = locationEvent.location
    // Determine which mouse event type should be generated.
    let eventType: CGEventType
    if button == 0 {
        if isDown {
            eventType = .leftMouseDown
        } else {
            eventType = .leftMouseUp
        }
    } else if button == 1 {
        if isDown {
            eventType = .rightMouseDown
        } else {
            eventType = .rightMouseUp
        }
    } else {
        if isDown {
            eventType = .otherMouseDown
        } else {
            eventType = .otherMouseUp
        }
    }
    // Convert the numeric button ID into a CGMouseButton.
    guard let mouseButton = CGMouseButton(rawValue: UInt32(button)) else {
        return
    }
    // Construct the mouse event at the current cursor location.
    guard let mouseEvent = CGEvent(
        mouseEventSource: nil,
        mouseType: eventType,
        mouseCursorPosition: cursorPosition,
        mouseButton: mouseButton
    ) else {
        return
    }
    mouseEvent.setIntegerValueField(.eventSourceUserData, value: SALLY_INJECTED_TAG)
    // Send the event into the HID event stream so the system
    // treats it like a real mouse input
    mouseEvent.post(tap: .cghidEventTap)
}