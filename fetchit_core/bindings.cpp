#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <string>
#include <vector>

// Forward declarations
std::vector<std::string> extract_urls_from_sitemap(const std::string& xml_content);
bool add_and_check_url(const std::string& url);

namespace py = pybind11;

PYBIND11_MODULE(fetchit_core, m) {
    m.doc() = "fetchit_core: C++ extension for fast parsing and deduplication"; // optional module docstring

    m.def("extract_urls_from_sitemap", &extract_urls_from_sitemap, "Extract URLs from sitemap XML quickly",
          py::arg("xml_content"));

    m.def("add_and_check_url", &add_and_check_url, "Atomically add a URL to the global visited set and check if it was newly added",
          py::arg("url"));
}
