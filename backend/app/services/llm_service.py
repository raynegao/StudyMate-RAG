from __future__ import annotations

from openai import OpenAI, OpenAIError

from app.core.config import settings


def _get_deepseek_client() -> OpenAI:
    if not settings.deepseek_api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY 环境变量，无法调用 DeepSeek。")

    return OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


def complete_answer(prompt: str) -> str:
    client = _get_deepseek_client()
    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            messages=[
                {
                    "role": "system",
                    "content": "你是 StudyMate，一名严谨的课程资料问答助手。",
                },
                {"role": "user", "content": prompt},
            ],
        )
    except OpenAIError as exc:
        raise RuntimeError(f"DeepSeek chat 调用失败：{exc}") from exc
    return response.choices[0].message.content or ""
