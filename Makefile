# Makefile for Python project

.DELETE_ON_ERROR:
.PHONY: FORCE
.PRECIOUS:
.SUFFIXES:

SHELL:=/bin/bash -e -o pipefail
SELF:=$(firstword $(MAKEFILE_LIST))

PKG=eutils
PKGD=$(subst .,/,${PKG})
PYV:=3.11
VEDIR=venv/${PYV}

UNAME = $(shell uname)
ifeq (${UNAME},Darwin)
    _XRM_R:=
else
    _XRM_R:=r
endif
XRM=xargs -0${_XRM_R} rm

############################################################################
#= BASIC USAGE
default: help

#=> help -- display this help message
help:
	@sbin/makefile-extract-documentation "${SELF}"


############################################################################
#= SETUP, INSTALLATION, PACKAGING

#=> venv: make a Python 3 virtual environment & install basic dependencies
.PHONY: venv/%
venv/%:
	python$* -m venv $@; \
	. $@/bin/activate; \
	python -m ensurepip --upgrade; \
	pip install --upgrade pip setuptools; \
	pip install .

#=> develop: install package in develop mode
.PHONY: develop
develop:
	pip install -e .[dev,test]

#=> devready: create venv, install prerequisites, install pkg in develop mode
.PHONY: devready
devready:
	make ${VEDIR} && source ${VEDIR}/bin/activate && make develop
	@echo '################################################################'
	@echo '###  `source ${VEDIR}/bin/activate` to use this environment  ###'
	@echo '################################################################'

#=> install: install package
#=> bdist bdist_egg bdist_wheel build sdist: distribution options
.PHONY: bdist bdist_egg bdist_wheel build build_sphinx sdist install
bdist bdist_egg bdist_wheel build sdist install: %:
	python setup.py $@

.PHONY: start
start:
	PYV=$(PYV) VEDIR=$(VEDIR) bash ./startup.sh

.PHONY: start-dev
start-dev:
	PYV=$(PYV) VEDIR=$(VEDIR) DEV_MODE=true bash ./startup.sh


############################################################################
#= TESTING
# see test configuration in setup.cfg

#=> cqa: execute code quality tests
cqa:
	ruff check src
	black --check src
	bandit -ll -r src

#=> test: execute tests
.PHONY: test
test:
	python -m pytest tests

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

#=> clean: remove temporary and backup files
.PHONY: clean
clean:
	find . \( -name \*~ -o -name \*.bak \) -print0 | ${XRM}

#=> cleaner: remove files and directories that are easily rebuilt
.PHONY: cleaner
cleaner: clean
	rm -rf .cache *.egg-info .pytest_cache build dist doc/_build htmlcov
	find . \( -name \*.pyc -o -name \*.orig -o -name \*.rej \) -print0 | ${XRM} -fr
	find . -name __pycache__ -print0 | ${XRM} -fr

#=> cleanest: remove files and directories that require more time/network fetches to rebuild
.PHONY: cleanest
cleanest: cleaner
	rm -fr .eggs .tox venv


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
