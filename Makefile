SHELL := /bin/bash
PY ?= python3

VERSION := $(shell cat VERSION 2>/dev/null || echo 0.0.0)
TAG := $(shell $(PY) -c "import json;print(json.load(open('upstream.lock.json'))['tag'])" 2>/dev/null)
UPSTREAM_VERSION := $(shell $(PY) -c "import json;print(json.load(open('upstream.lock.json'))['version'])" 2>/dev/null)

PACK := pack
SIZE := 512
ZIP := dist/MaterialIconTheme-$(VERSION).zip

.PHONY: help build check verify dist vendor preview clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "  upstream: $(TAG) (pinned in upstream.lock.json)"
	@echo "  version:  $(VERSION)"

build: ## Render the pack into pack/ (needs Inkscape, or --renderer copy)
	$(PY) scripts/build.py --size $(SIZE)

check: ## Validate mappings/ against pack/ and the vendored upstream (fast, no rendering)
	$(PY) scripts/build.py --check --size $(SIZE)

verify: ## Validate the built pack (sizes, names, thumbnails, mappings)
	$(PY) scripts/verify.py --size $(SIZE)

dist: build verify ## Build and zip the distributable into dist/
	./scripts/package.sh

vendor: ## Refresh vendor/material-icon-theme from the pinned tag
	./scripts/fetch-upstream.sh --force

preview: ## Refresh docs/preview.png from the generated thumbnail
	cp $(PACK)/FileIcons/MaterialIconTheme/Thumbnail.png docs/preview.png
	@echo "docs/preview.png updated"

clean: ## Remove dist/ and One Commander scale caches
	rm -rf dist
	find $(PACK) -type d -regex '.*/[0-9]+' -prune -exec rm -rf {} + 2>/dev/null || true
