# Sally Clicks Makefile
# Run 'make' to build the engine.
# Run 'make run' to build and launch the app.
# Run 'make package' to bundle everything into a Mac .app file.

SWIFTC = swiftc
SWIFT_FILE = sally_engine.swift
DYLIB = libsally.dylib
PYTHON = python

.PHONY: all build run clean package

# Default command when you just type 'make'
all: build

# Compiles the Swift code into the .dylib
build:
	@echo "Compiling Swift Engine..."
	$(SWIFTC) $(SWIFT_FILE) -emit-library -O -o $(DYLIB) \
		-sdk $$(xcrun --show-sdk-path) \
		-target arm64-apple-macosx12.0
	@echo "libsally.dylib created successfully."

# Builds the engine and runs the Python app
run: build
	@echo "Launching Sally Clicks..."
	$(PYTHON) main.py

# Cleans up compiled files and caches
clean:
	@echo "🧹 Cleaning up..."
	rm -f $(DYLIB)
	rm -rf __pycache__ */__pycache__
	rm -rf build dist *.spec
	@echo "✨ Clean complete."

# Bundles the app for end-users using PyInstaller
package: build
	@echo "Packaging for macOS..."
	pyinstaller --noconfirm --windowed --name "Sally Clicks" --add-binary "$(DYLIB):." main.py
	@echo "Packaging complete! Check the 'dist' folder."