CXX = g++
CXXFLAGS = -O3 -Wall -shared -std=c++17 -fPIC `python3 -m pybind11 --includes`
SUFFIX = `python3-config --extension-suffix`
TARGET = build/fetchit_core$(SUFFIX)
SRC = fetchit_core/bindings.cpp fetchit_core/sitemap_parser.cpp fetchit_core/url_manager.cpp

all: $(TARGET)

$(TARGET): $(SRC)
	@mkdir -p build
	@echo "Compiling C++ extension..."
	$(CXX) $(CXXFLAGS) $(SRC) -o $(TARGET)
	@cp $(TARGET) fetchit/
	@echo "Compilation successful."

clean:
	rm -rf build
	rm -f fetchit/fetchit_core*.so

install: $(TARGET)
	@echo "Installing FetchIt system-wide..."
	@if command -v pacman > /dev/null; then \
		echo "Arch Linux detected. Installing dependencies via pacman..."; \
		pacman -S --noconfirm --needed pybind11 python-aiohttp python-beautifulsoup4 python-markdownify python-tqdm python-lxml; \
		pip3 install --no-deps --break-system-packages .; \
	else \
		pip3 install .; \
	fi
	@echo "Installation complete!"
