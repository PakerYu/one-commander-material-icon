SHELL := /bin/bash
PY ?= python3

VERSION := $(shell cat VERSION 2>/dev/null || echo 0.0.0)
TAG := $(shell $(PY) -c "import json;print(json.load(open('upstream.lock.json'))['tag'])" 2>/dev/null)
UPSTREAM_VERSION := $(shell $(PY) -c "import json;print(json.load(open('upstream.lock.json'))['version'])" 2>/dev/null)

PACK := pack
SIZE := 512
MAIN_FOLDER_SIZE := 64
ZIP := dist/MaterialIconTheme-$(VERSION).zip
UPSTREAM_LICENSE := LICENSES/material-icon-theme-MIT.txt

.PHONY: help build check verify notices licenses package dist vendor preview clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "  upstream: $(TAG) (pinned in upstream.lock.json)"
	@echo "  version:  $(VERSION)"
	@echo "  license:  MIT (see LICENSE, ATTRIBUTION.md, LICENSES/)"

build: ## Render the pack into pack/ (needs Inkscape, or --renderer copy)
	$(PY) scripts/build.py --size $(SIZE) --main-folder-size $(MAIN_FOLDER_SIZE)

check: ## Validate mappings/ against pack/ and the vendored upstream (fast, no rendering)
	$(PY) scripts/build.py --check --size $(SIZE) --main-folder-size $(MAIN_FOLDER_SIZE)

verify: ## Validate the built pack (sizes, names, thumbnails, MainFolderIcon, mappings)
	$(PY) scripts/verify.py --size $(SIZE) --main-size $(MAIN_FOLDER_SIZE)

notices: ## Check license notices, and the notices inside $(ZIP) when it exists
	./scripts/check-notices.sh $(if $(wildcard $(ZIP)),--zip $(ZIP),)

licenses: ## Refresh $(UPSTREAM_LICENSE) from the vendored upstream license
	cp vendor/material-icon-theme/LICENSE $(UPSTREAM_LICENSE)
	@cmp -s vendor/material-icon-theme/LICENSE $(UPSTREAM_LICENSE) && echo "refreshed $(UPSTREAM_LICENSE)"

# package.sh runs check-notices.sh itself (repository files first, then the finished
# archive), so the zip-aware `notices` target is deliberately not a prerequisite here.
package: verify ## Zip the committed pack/ without re-rendering (CI-friendly)
	./scripts/package.sh

dist: build verify ## Render, validate, and zip the distributable into dist/
	./scripts/package.sh

vendor: ## Refresh vendor/material-icon-theme from the pinned tag
	./scripts/fetch-upstream.sh --force

preview: ## Refresh docs/preview.png from the generated thumbnail
	cp $(PACK)/FileIcons/MaterialIconTheme/Thumbnail.png docs/preview.png
	@echo "docs/preview.png updated"

clean: ## Remove dist/ and One Commander scale caches
	rm -rf dist
	find $(PACK) -type d -regex '.*/[0-9]+' -prune -exec rm -rf {} + 2>/dev/null || true
