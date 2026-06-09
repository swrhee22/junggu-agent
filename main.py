import os
import sys
import logging

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional

from utils import *
from config import Config

# async
import asyncio
import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",  # 날짜와 시간 형식 (연-월-일 시:분:초)
    force=True,  # 중복 출력 방지 (Jupyter에서 필요)
)

logger = logging.getLogger(__name__)

# os.environ["env"] = "STG"
config = Config()

PREPROCESSING_URL = config.PREPROCESSING_URL
EXTRACT_EVAL_URL = config.EXTRACT_EVAL_URL
# PREPROCESSING_URL = "http://net20240020-svc.inference.svc:8000/process"
# EXTRACT_EVAL_URL = "http://net20250008-svc.inference.svc:8000/evaluate"


# * Unit Master Table
file_name = os.getenv("unit_path", "unit_master_table_dev_250519.csv")
UNIT_MASTER_PATH = f"/datasets/DTS2024000005/data/{file_name}"
unit_master = pd.read_csv(UNIT_MASTER_PATH).fillna("None")

logger.info(f"{config.env} LMS DB...")
logger.info(f"PREPROCESSING_URL: {PREPROCESSING_URL}")
logger.info(f"EXTRACT_EVAL_URL: {EXTRACT_EVAL_URL}")
logger.info(f"SAVE_URL: {config.SAVE_URL}")
logger.info(f"HEADERS: {config.HEADERS}")
logger.info(f"UNIT_MASTER_PATH: {UNIT_MASTER_PATH}")

# ============================
# FAST API SETTING
# ============================
tags_metadata = [
    {
        "name": "Client",
        "description": "Virtual Client",
    },
]


app = FastAPI(
    title="[AEON] Virtual Client",
    description="Virtual client for load testing",
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


class Request(BaseModel):
    script: str = Field(
        examples=[
            "WEBVTT\n\n1\n00:03:06.370 --> 00:03:07.290\nTeacher: Hello!\n\n2\n00:03:15.830 --> 00:03:17.220\nTeacher: Oh, hello!\n\n3\n00:03:19.680 --> 00:03:21.140\nTeacher: Can you hear my voice?\n\n4\n00:03:24.200 --> 00:03:25.820\nTeacher: Okay, one moment."
        ]
    )
    customer_uid: Optional[int] = Field(examples=[158])
    lesson_uid: Optional[int] = Field(examples=[430])
    textbook_name: Optional[str] = Field(examples=["【文法別】日常英会話・入門"])
    unit_uid: Optional[int] = Field(examples=[564])
    unit_number: Optional[str] = Field(examples=["Kick Off Unit 9 Day 2"])
    teacher: Optional[str] = Field(examples=["Teacher"])
    student: Optional[str] = Field(examples=["Student"])


# ==============================================
# ENDPOINT
# ==============================================


# /evaluate 엔드포인트에서 요청을 한 쪽에 잘 받았다고 먼저 응답하고 다음 로직을 처리할 수 있나요?
@app.post(
    "/evaluate",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "성공적인 응답",
            "content": {
                "application/json": {
                    "example": {
                        "result": "SUCCESS",
                        "message": "成功",
                    }
                }
            },
        },
        400: {
            "description": "클라이언트 오류 (잘못된 입력값 또는 필수 키 누락)",
            "content": {
                "application/json": {
                    "example": {
                        "result": "FAILURE",
                        "message": "失敗: 입력값 오류",
                    }
                }
            },
        },
        500: {
            "description": "서버 오류",
            "content": {
                "application/json": {
                    "example": {
                        "result": "FAILURE",
                        "message": "失敗: 서버 오류",
                    }
                }
            },
        },
    },
)
async def evaluate_vtt(request: Request, background_tasks: BackgroundTasks):
    try:
        request_dict = request.model_dump()
        logger.info(
            f"request:\ncustomer_uid: {request_dict['customer_uid']}\n\tlesson_uid: {request_dict['lesson_uid']}\n\ttextbook_name: {request_dict['textbook_name']}\n\tunit_uid: {request_dict['unit_uid']}\n\tunit_number: {request_dict['unit_number']}"
        )

        # 스크립트 길이가 너무 짧으면 평가 제외
        if len(request_dict["script"].strip()) < 500:
            logger.info(
                f"失敗: 스크립트가 너무 짧아, 평가할 수 없습니다. ( lesson_uid: {request_dict['lesson_uid']} ) === 스크립트 길이: {len(request_dict['script'].strip())}"
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "result": "FAILURE",
                    "message": f"失敗: 스크립트가 너무 짧아, 평가할 수 없습니다. 스크립트 길이: {len(request_dict['script'].strip())}",
                },
            )

        # unit master table에 존재하지 않는 교재 | 유닛인 경우 평가 제외
        check = check_unit_master_table(
            unit_master, request_dict["textbook_name"], request_dict["unit_uid"]
        )
        if not check:
            logger.info(
                f"失敗: 해당 {request_dict['textbook_name']}, {request_dict['unit_uid']} 조합의 메타 정보가 존재하지 않습니다. ( lesson_uid: {request_dict['lesson_uid']} )"
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "result": "FAILURE",
                    "message": f"失敗: 해당 textbook_name, unit_number 조합의 메타 정보가 존재하지 않습니다.",
                },
            )

        # 요청 접수 확인 메시지 즉시 반환
        confirmation = {"result": "SUCCESS", "message": "成功"}

        # 백그라운드에서 실행할 작업 정의
        background_tasks.add_task(process_evaluation, request_dict)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=confirmation,
        )

    except ValueError as e:
        # 입력값 오류 - 400 Bad Request
        logger.error(f"Invalid input error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "result": "FAILURE",
                "message": f"失敗: {str(e)}",
            },
        )

    except KeyError as e:
        # 필수 키 누락 - 400 Bad Request
        logger.error(f"Missing key error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "result": "FAILURE",
                "message": f"失敗: {str(e)}",
            },
        )

    except Exception as e:
        # 기타 서버 오류 - 500 Internal Server Error
        logger.error(f"Error generating schedule: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "result": "FAILURE",
                "message": f"失敗: {str(e)}",
            },
        )


async def process_evaluation(request_dict):
    try:
        logger.info(
            f"Starting preprocessing for lesson_uid: {request_dict['lesson_uid']}"
        )
        script = request_dict.get("script")

        # 줄바꿈 문자 통일
        script = script.replace("\r\n", "\n")

        logger.info(
            f"Calling preprocessing service for lesson_uid: {request_dict['lesson_uid']}"
        )
        script_prep = (await async_process({"script": script}, url=PREPROCESSING_URL))[
            "script"
        ]
        logger.info(
            f"Preprocessing completed for lesson_uid: {request_dict['lesson_uid']}"
        )

        # evaluate script
        logger.info(f"Starting evaluation for lesson_uid: {request_dict['lesson_uid']}")
        # * textbook_name와 unit_uid를 활용하도록 수정 완료! (250521)
        eval_input = generate_input_from_meta(
            textbook_name=request_dict["textbook_name"],
            unit_uid=request_dict["unit_uid"],
            # unit_number=request_dict["unit_number"],
            unit_master=unit_master,
        )
        eval_input["script"] = script_prep
        eval_input["teacher"] = request_dict["teacher"]
        eval_input["student"] = request_dict["student"]
        eval_input["lesson_uid"] = request_dict["lesson_uid"]

        # logger.info(f"eval_input: {eval_input}")

        eval_result = await async_process(eval_input, url=EXTRACT_EVAL_URL)

        #! Bad Example가 없는 경우 대체 문장 추가
        if not eval_result["Evaluate"].get("bad_examples"):
            eval_result["Evaluate"]["bad_examples"] = []
            eval_result["Evaluate"]["bad_example_reason"] = [
                "良くない例は特にありませんでした。素晴らしい！"
            ]
        logger.info("[Done] evaluate script")

        # result
        result_dict = {}

        result_dict["customer_uid"] = request_dict["customer_uid"]
        result_dict["lesson_uid"] = request_dict["lesson_uid"]

        scores = {}
        scores["vocabulary_score"] = eval_result["Evaluate"]["scores"]["vocabulary"]
        scores["grammar_score"] = eval_result["Evaluate"]["scores"]["grammar"]
        scores["pronunciation_score"] = eval_result["Evaluate"]["scores"][
            "pronunciation"
        ]
        scores["organization_score"] = eval_result["Evaluate"]["scores"]["organization"]
        scores["fluency_score"] = eval_result["Evaluate"]["scores"]["fluency"]
        scores["social_skills_score"] = eval_result["Evaluate"]["scores"][
            "social_skills"
        ]
        scores["strategy_score"] = eval_result["Evaluate"]["scores"]["strategy"]
        scores["endurance_score"] = eval_result["Evaluate"]["scores"]["endurance"]
        scores["contents_score"] = eval_result["Evaluate"]["scores"]["contents"]

        result_dict["scores"] = scores

        result_dict["goal"] = eval_result["Evaluate"]["goal"]
        result_dict["goal_achievement"] = eval_result["Evaluate"]["goal_achievement"]
        result_dict["goal_score"] = eval_result["Evaluate"]["goal_score"]
        result_dict["good_examples"] = eval_result["Evaluate"]["good_examples"]
        result_dict["good_example_reasons"] = eval_result["Evaluate"][
            "good_example_reason"
        ]
        result_dict["bad_examples"] = eval_result["Evaluate"]["bad_examples"]
        result_dict["bad_example_reasons"] = eval_result["Evaluate"][
            "bad_example_reason"
        ]
        result_dict["overall_evaluation"] = eval_result["Evaluate"]["total_evaluation"]

        logger.info(
            f"Starting save operation for lesson_uid: {request_dict['lesson_uid']}"
        )
        # 결과 저장
        await save_result(result_dict)
        logger.info(
            f"Completed all operations for lesson_uid: {request_dict['lesson_uid']}"
        )

    except Exception as e:
        import traceback

        logger.error(
            f"Background task failed for lesson_uid {request_dict.get('lesson_uid', 'unknown')}: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        )

    return None


async def save_result(result_dict):
    request_url = config.SAVE_URL
    headers = config.HEADERS

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                request_url, headers=headers, json=result_dict
            ) as response:
                if response.status == 200:
                    response_text = await response.text()
                    logger.info(f"결과가 성공적으로 저장되었습니다.")
                    return response
                else:
                    error_text = await response.text()
                    logger.error(
                        f"결과 저장 실패. 상태 코드: {response.status}, 오류: {error_text}"
                    )
                    return None
    except Exception as e:
        logger.error(f"요청 중 오류 발생: {str(e)}")
        return None
