# AI Mask Banana

## Overview

This project is a simple web application using a FastAPI backend and a frontend built with HTML, CSS, and JavaScript.

The purpose of this project is to test out the in-panting capability of the gemini 2.5 image gen preview model (a.k.a. Nano Banana) using a mask. 

## Setup and Usage

This project uses a `Makefile` to automate setup and execution.

### Prerequisites

*   Python 3
*   `make`

### Installation

To install the dependencies, run:

```bash
make install
```

This will create a Python virtual environment in a `venv` directory and install the required packages from `requirements.txt`.

### Running the Application

To run the web server, use the following command:

```bash
make run
```

This will start the FastAPI server. You can then access the application at [http://127.0.0.1:8000](http://127.0.0.1:8000).

### Cleaning Up

To remove the virtual environment, run:

```bash
make clean
```
