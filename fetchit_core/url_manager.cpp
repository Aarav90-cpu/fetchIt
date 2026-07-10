#include <string>
#include <unordered_set>
#include <mutex>

static std::unordered_set<std::string> visited_urls;
static std::mutex mtx;

// Atomically checks if URL exists. If not, adds it and returns true.
// Otherwise returns false.
bool add_and_check_url(const std::string& url) {
    std::lock_guard<std::mutex> lock(mtx);
    auto result = visited_urls.insert(url);
    return result.second; // true if insertion took place
}
