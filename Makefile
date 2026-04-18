# Copyright (C) 2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

.PHONY: build list-image clean push static-code-analysis tests test-unit test-integration test-component compose-config compose-smoke compose-parity compose-bootstrap compose-bootstrap-reset compose-bootstrap-seed-weights compose-prepare-certs
.DEFAULT_GOAL := build
PROJECTS = interactive_ai platform web_ui web_ui/dex_templates

build-image:
	echo "Building images for all projects..."
	@for dir in $(PROJECTS); do \
		echo "Running make build-image in $$dir..."; \
		$(MAKE) -C $$dir build-image; \
	done

clean:
	echo "Cleaning all projects..."	
	@for dir in $(PROJECTS); do \
		echo "Running make clean in $$dir..."; \
		$(MAKE) -C $$dir clean; \
	done

list-image:
	@for dir in $(PROJECTS); do \
		$(MAKE) -C $$dir list-image; \
	done

publish-image:
	echo "Pushing all projects..."
	@for dir in $(PROJECTS); do \
		echo "Running make publish-image in $$dir..."; \
		$(MAKE) -C $$dir publish-image; \
	done

static-code-analysis:
	echo "Running static code analysis for all projects..."
	@for dir in $(PROJECTS); do \
		echo "Running make static-code-analysis in $$dir..."; \
		$(MAKE) -C $$dir static-code-analysis; \
	done

tests:
	echo "Running tests for all projects..."
	@for dir in $(PROJECTS); do \
		echo "Running make tests in $$dir..."; \
		$(MAKE) -C $$dir tests; \
	done

test-unit:
	echo "Running unit tests for all projects..."
	@for dir in $(PROJECTS); do \
		echo "Running make test-unit in $$dir..."; \
		$(MAKE) -C $$dir test-unit; \
	done

test-integration:
	echo "Running integration tests for all projects..."
	@for dir in $(PROJECTS); do \
		echo "Running make test-integration in $$dir..."; \
		$(MAKE) -C $$dir test-integration; \
	done	

test-component:
	echo "Running component tests for all projects..."
	@for dir in $(PROJECTS); do \
		echo "Running make test-component in $$dir..."; \
		$(MAKE) -C $$dir test-component; \
	done

compose-config:
	docker compose config --quiet

compose-smoke:
	bash infrastructure/compose-smoke.sh

compose-parity:
	bash infrastructure/compose-parity.sh

compose-bootstrap:
	bash infrastructure/compose-bootstrap.sh

compose-bootstrap-reset:
	bash infrastructure/compose-bootstrap.sh --reset

compose-bootstrap-seed-weights:
	bash infrastructure/compose-bootstrap.sh --seed-weights

compose-prepare-certs:
	@echo "Cert preparation is handled by unified init service (geti_init)."
