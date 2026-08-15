# AI Mask Banana

[![Subscribe on YouTube](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.socialcounts.org%2Fyoutube-live-subscriber-count%2FUC3XbEkSbPOzHvqNBrjNIu7A&query=%24.counters.api.subscriberCount&label=Subscribe&suffix=%20subscribers&color=FF0000&logo=youtube&logoColor=white&style=for-the-badge)](https://www.youtube.com/@practicalgcp2780?sub_confirmation=1)
[![Videos](https://img.shields.io/badge/90%2B_videos-Watch_all-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/playlist?list=UU3XbEkSbPOzHvqNBrjNIu7A)

_Code from the [PracticalGCP](https://www.youtube.com/@practicalgcp2780) YouTube channel._


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
