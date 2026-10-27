"""Check the configured Chat Completions endpoint with a non-customer test message."""

import json

from openai import APIError, OpenAI

from customer_service_qa.config import Settings


def main() -> int:
    settings = Settings()
    if not settings.has_llm_api_key:
        print("Missing API key: set DASHSCOPE_API_KEY (or LLM_API_KEY) in the local .env.")
        return 2
    try:
        with OpenAI(
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        ) as client:
            completion = client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": "Reply with the single word OK."}],
                max_tokens=64,
                extra_body=settings.llm_extra_body or None,
            )
        if not completion.choices or not completion.choices[0].message.content:
            print("The endpoint returned no text. Check this model's response format.")
            return 1
    except APIError as error:
        # Do not expose exception bodies, request headers, or credentials.
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "http_status": getattr(error, "status_code", None),
                }
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": "connected",
                "model": settings.llm_model,
                "note": "Chat completion succeeded; structured workflow still needs testing.",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
