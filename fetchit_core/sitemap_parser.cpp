#include <string>
#include <vector>

// Fast string matching for <loc> tags in sitemap XML files
// This avoids the overhead of a full XML parser for simple sitemaps
std::vector<std::string> extract_urls_from_sitemap(const std::string& xml_content) {
    std::vector<std::string> urls;
    size_t pos = 0;
    
    while ((pos = xml_content.find("<loc>", pos)) != std::string::npos) {
        pos += 5; // length of "<loc>"
        size_t end_pos = xml_content.find("</loc>", pos);
        if (end_pos != std::string::npos) {
            urls.push_back(xml_content.substr(pos, end_pos - pos));
            pos = end_pos + 6; // length of "</loc>"
        } else {
            break;
        }
    }
    
    return urls;
}
