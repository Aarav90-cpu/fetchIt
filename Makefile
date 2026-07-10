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
	python3 -m pip install .
	@echo "Installation complete!"

