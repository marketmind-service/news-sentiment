import re
import json
import textwrap
from typing import Optional, Tuple

from langchain_core.messages import SystemMessage, HumanMessage
from config import query, query2
from state import NewsState


async def extract_company_and_items(prompt: str) -> Tuple[Optional[str], Optional[int]]:
    messages = [
        SystemMessage(
            content=textwrap.dedent("""
            You extract a company (ticker or name) and how many news items to fetch
            from a user's stock news request.

            Output EXACTLY one JSON object, with no spaces and no newline:
            {"company":"<VALUE>","items":<N>}

            Company Rules:
            - VALUE can be:
              * A stock ticker (NVDA, AAPL, RY.TO, SHOP.TO, QQQ)
              * OR an official company/index name (Nvidia, S&P 500, Royal Bank of Canada)
            - Fix obvious typos.
            - Map vague phrases to the most likely company, for example:
              "the iphone company" -> "Apple"
              "google stock" -> "Google" or "Alphabet"
              "NVDA stock" -> "NVDA"
            - If multiple companies appear, pick the MAIN one the user is asking about.
            - If you truly cannot infer any company, use null.
            
            Items Rules:
            You extract a company (ticker or name) and how many news items to fetch
            from a user's stock news request.

            Output EXACTLY one JSON object, with no spaces and no newline:
            {"company":"<VALUE>","items":<N>}

            Rules:
            - Company VALUE can be:
              * A stock ticker (NVDA, AAPL, RY.TO, SHOP.TO, QQQ)
              * OR an official company name (Nvidia, Apple, Royal Bank of Canada)
            - Fix obvious typos.
            - Map vague phrases to the most likely company, for example:
              "the iphone company" -> "Apple"
              "google stock" -> "Google" or "Alphabet"
              "NVDA stock" -> "NVDA"
            - If multiple companies appear, pick the MAIN one the user is asking about
            - If you truly cannot infer any company, use null
            - No explanations. No extra keys. No spaces anywhere
            
            Rules:
            - Extract explicit amounts ("top 5","last 20","show 3 headlines")
            - Must be a positive integer
            - If no number found, use null
            
            No explanations. No extra keys. No spaces anywhere.
            """).strip()
        ),
        HumanMessage(content=f"Prompt: {prompt}")
    ]

    response = query2.invoke(messages)
    raw = response.content if isinstance(response.content, str) else str(response.content)

    company: Optional[str] = None
    items: Optional[int] = None

    try:
        start, end = raw.find("{"), raw.rfind("}")
        obj = json.loads(raw[start:end + 1])

        c = obj.get("company")
        if isinstance(c, str):
            c = c.strip()
            if c:
                company = c

        n = obj.get("items")
        if isinstance(n, int) and n > 0:
            items = n

    except Exception:
        pass

    # fallbacks
    if company is None:
        m = re.findall(r"\b[A-Z]{1,5}(?:\.[A-Z]{1,3})?\b", prompt)
        if m:
            company = m[0].strip()
        elif prompt.strip():
            company = prompt.strip()

    if items is None:
        m = re.search(r"\b(\d{1,3})\b", prompt)
        if m:
            try:
                n = int(m.group(1))
                if n > 0:
                    items = n
            except ValueError:
                pass

    return company, items


async def parse_input(state: NewsState) -> NewsState:
    print("parse_input")

    company, items = await extract_company_and_items(state.prompt)

    default_items = getattr(state, "items", 20)

    print(f"Company: {company}")
    print(f"Items:   {items or default_items}")

    return state.model_copy(update={
        "company": company or "",
        "items": items or default_items,
    })