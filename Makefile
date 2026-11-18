.PHONY: install uninstall clean

install:
	@echo "Installing FetchIt..."
	@if command -v pacman > /dev/null; then \
		echo "Arch Linux detected. Installing dependencies via pacman..."; \
		pacman -S --noconfirm --needed python-aiohttp python-beautifulsoup4 python-markdownify python-tqdm python-lxml; \
		pip3 install --no-deps --break-system-packages .; \
	else \
		pip3 install .; \
	fi
	@echo "Installation complete!"

uninstall:
	@echo "Uninstalling FetchIt..."
	@if command -v pacman > /dev/null; then \
		pip3 uninstall --break-system-packages -y fetchit-md; \
	else \
		pip3 uninstall -y fetchit-md; \
	fi
	@echo "Uninstallation complete!"

clean:
	rm -rf build dist *.egg-info
