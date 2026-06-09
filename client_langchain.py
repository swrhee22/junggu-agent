import json
import utils
import logging

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.base import Runnable
from langchain_core.beta.runnables.context import Context
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from utils import convert_extraction_instruction


load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",  # 시간 형식
)
logger = logging.getLogger(__name__)


class ScoreResult(BaseModel):
    vocabulary: int = Field(description="Vocabulary score")
    grammar: int = Field(description="Grammar score")
    pronunciation: int = Field(description="Pronunciation score")
    organization: int = Field(description="Organization score")
    fluency: int = Field(description="Fluency score")
    social_skills: int = Field(description="Social skills score")
    strategy: int = Field(description="Strategy score")
    endurance: int = Field(description="Endurance score")
    contents: int = Field(description="Contents score")


class EvaluateResult(BaseModel):
    scores: ScoreResult = Field(description="All evaluation scores")
    goal: str = Field(description="Goal of this lesson")
    goal_achievement: str = Field(description="Goal achievement")
    goal_score: int = Field(description="Goal score")
    good_examples: list[str] = Field(
        description="Top 1-4 good examples of correct language usage",
        min_length=0,
        max_length=4,
    )
    good_example_reason: list[str] = Field(
        description="Detailed and encouraging description of what was done well in each good example",
        min_length=0,
        max_length=4,
    )
    bad_examples: list[str] = Field(
        description="0-3 most important points for improvement. These sentences must not be identical to those in good_examples.",
        min_length=0,
        max_length=3,
    )
    bad_example_reason: list[str] = Field(
        description="Friendly, constructive feedback on how to improve these areas, including specific practice suggestions and examples of correct usage",
        min_length=0,
        max_length=3,
    )
    total_evaluation: str = Field(
        description="Comprehensive evaluation starting with positive achievements and including actionable suggestions"
    )


def build_custom_chain(
    inputs: dict,
) -> Runnable:

    extraction_template = utils.load_prompt_template(name="extraction", is_yaml=True)
    evaluation_template = utils.load_prompt_template(name="evaluation", is_yaml=True)

    inputs["extraction_instruction"] = convert_extraction_instruction(
        inputs["category"], inputs["type"]
    )

    extraction_prompt = extraction_template.partial(**inputs)
    evaluation_prompt = evaluation_template.partial(
        **{k: v for k, v in inputs.items() if k not in ["script"]}
    )

    extract_model = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=None)
    evaluate_model = ChatOpenAI(
        model="gpt-4o", temperature=0, max_tokens=None
    ).with_structured_output(EvaluateResult)

    chain = (
        extraction_prompt
        | extract_model
        | Context.setter("Extract")  # 중간 결과를 "Extract"라는 키로 저장
        | {"extracted_script": StrOutputParser()}
        | evaluation_prompt
        | evaluate_model
        | {
            "Extract": Context.getter("Extract") | StrOutputParser(),
            "Evaluate": RunnablePassthrough(),
        }
    )

    return chain


async def generator(rqst):
    logger.info(
        "!!!!!!!!Chain invocation started Generator!!!!!!!!"
    )  # 비동기 함수 시작 로깅
    chain = build_custom_chain(rqst)

    response = chain.stream({})

    generated_text = ""

    for token in response:
        generated_text += token.content
        result = {
            "token": {"text": token.content, "special": False},
            "generated_text": None,
        }
        ret = "data: %s\n" % (json.dumps(result, ensure_ascii=False))
        yield ret


async def async_chat_completions(rqst):
    logger.info(
        f"\tChain invocation started for lesson_uid: {rqst['lesson_uid']}"
    )  # 비동기 함수 시작 로깅
    chain = build_custom_chain(rqst)
    response = await chain.ainvoke({})
    logger.info(
        f"\tChain invocation finished for lesson_uid: {rqst['lesson_uid']}"
    )  # 비동기 함수 종료 로깅
    return response
