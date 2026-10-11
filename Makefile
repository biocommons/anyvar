# Makefile for Python project

.DELETE_ON_ERROR:
.PHONY: FORCE
.PRECIOUS:
.SUFFIXES:

.DEFAULT_GOAL := help
default: help

define INFO_MESSAGE
	@echo "⏩\033[1;38;5;208m$(1)\033[0m"
endef

############################################################################
#= BASIC USAGE

.PHONY: help
help: ## Display help message
	@./sbin/makefile-extract-documentation ${MAKEFILE_LIST}

############################################################################
#= SETUP, INSTALLATION, PACKAGING

install: devready
.PHONY: devready
devready: ## Prepare local dev env: Create virtual env, install the pre-commit hooks
	$(call INFO_MESSAGE, Prepare local dev env: Create virtual env and install the pre-commit hooks)
	uv sync --dev
	uv run pre-commit install
	$(call INFO_MESSAGE, Activate the virtual env with \`source .venv/bin/activate\`)

.PHONY: build
build: ## Build package
	$(call INFO_MESSAGE, "Build package")
	rm -fr dist
	uv build

.PHONY: publish
publish: build ## Publish package to PyPI
	$(call INFO_MESSAGE, "Publish package to PyPI")
	uv publish  # Requires UV_PUBLISH_TOKEN or Trusted Publishing setup

############################################################################
#= FORMATTING, TESTING, AND CODE QUALITY

.PHONY: testready
testready:
	pip install -e '.[postgres,queueing,test]'

.PHONY: cqa
cqa: ## Run code quality assessments
	$(call INFO_MESSAGE, "Checking lock file consistency")
	uv lock --locked
	$(call INFO_MESSAGE, "Linting and reformatting files")
	uv run pre-commit run
	$(call INFO_MESSAGE, "Checking for obsolete dependencies")
	uv run deptry src

.PHONY: test
test: ## Test the code with pytest
	@echo "🚀 Testing code: Running pytest"
	uv run pytest

############################################################################
#= UTILITY TARGETS

# N.B. Although code is stored in github, I use hg and hg-git on the command line
#=> reformat: reformat code with yapf and commit
.PHONY: reformat
reformat:
	@if ! git diff --cached --exit-code; then echo "Repository not clean" 1>&2; exit 1; fi
	yapf -i -r "${PKGD}" tests
	git commit -a -m "reformatted with yapf"

#=> docs -- make sphinx docs
.PHONY: docs
docs: develop
	# RTD makes json. Build here to ensure that it works.
	make -C docs html json

############################################################################
#= CLEANUP

.PHONY: clean
clean:  ## Remove temporary and backup files
	$(call INFO_MESSAGE, "Remove temporary and backup files")
	find . \( -name "*~" -o -name "*.bak" \) -exec rm -frv {} +

.PHONY: cleaner
cleaner: clean  ## Remove files and directories that are easily rebuilt
	$(call INFO_MESSAGE, "Remove files and directories that are easily rebuilt")
	rm -frv .cache .DS_Store .pytest_cache .ruff_cache build coverage.xml dist docs/_build site
	find . \( -name __pycache__ -type d \) -exec rm -frv {} +
	find . \( -name "*.pyc" -o -name "*.egg-info" \) -exec rm -frv {} +
	find . \( -name "*.orig" -o -name "*.rej" \) -exec rm -frv {} +

.PHONY: cleanest
cleanest: cleaner  ## Remove files and directories that can be rebuilt
	$(call INFO_MESSAGE, "Remove files and directories that can be rebuilt")
	rm -frv .eggs .tox .venv venv

.PHONY: distclean
distclean: cleanest  ## Remove untracked files and other detritus
	@echo "❌ Remove untracked files and other detritus -- Too dangerous... do this yourself"
	# git clean -df


## <LICENSE>
## Copyright 2016 Source Code Committers
##
## Licensed under the Apache License, Version 2.0 (the "License");
## you may not use this file except in compliance with the License.
## You may obtain a copy of the License at
##
##     http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.
## </LICENSE>
