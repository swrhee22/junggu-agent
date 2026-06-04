import os
import sys
import logging
import warnings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)

from apis.generate import generator
from apis.update import update
from apis.reschedule import rescheduler

tags_metadata = [
    {
        "name": "Lesson Scheduler",
        "description": "Generate a learning schedule.",
    },
]


app = FastAPI(
    title="[AEON] Lesson Scheduler",
    description="Generates a learning schedule based on the user's current level, target level, target skills, days/week, and hours/day.",
    version="1.0",
    # doc_url=None,
    # redoc_url=None,
    openapi_tags=tags_metadata,
    swagger_ui_parameters={"syntaxHighlight.theme": "obsidian"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(generator)
app.include_router(update)
app.include_router(rescheduler)