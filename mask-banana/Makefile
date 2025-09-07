# Makefile for the FastAPI project

VENV_NAME = venv
VENV_BIN = $(VENV_NAME)/bin
PYTHON = $(VENV_BIN)/python
PIP = $(VENV_BIN)/pip
UVICORN = $(VENV_BIN)/uvicorn

.PHONY: all install run clean

all: run

# Create virtual environment if it doesn't exist
$(VENV_NAME):
	python3 -m venv $(VENV_NAME)

# Install dependencies
install: $(VENV_NAME)
	$(PIP) install -r requirements.txt

# Run the server
run: install
	$(UVICORN) main:app --reload

# Remove the virtual environment
clean:
	rm -rf $(VENV_NAME)
